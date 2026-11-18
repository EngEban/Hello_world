"""
analyzer/services/data_service.py
Handles file parsing, sanitization, variable detection, and data preparation.
"""
import csv
import io
import json
import re
import hashlib
import tempfile
import os
from typing import Any

import numpy as np
import pandas as pd
import pyreadstat


# ── Constants ─────────────────────────────────────────────────────────────────
MAX_ROWS = 50_000
MAX_COLS = 500
MAX_CELLS = 1_000_000
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_JSON_NESTING = 64
# Common research-data formats.  Parsing remains in-memory and every format is
# subject to the same row, column, and size limits below.
ALLOWED_EXTENSIONS = {"csv", "tsv", "txt", "xlsx", "xls", "sav", "zsav", "por", "dta", "json"}
# An .xlsx is a zip; a few MB can expand to gigabytes ("zip bomb"), so the
# archive is inspected before openpyxl parses it.
MAX_XLSX_UNCOMPRESSED_BYTES = 150 * 1024 * 1024
MAX_XLSX_ENTRIES = 2_000


def _check_spreadsheet_before_parse(content: bytes, ext: str) -> None:
    """Reject oversized or over-wide workbooks before the expensive full parse."""
    if ext == "xlsx":
        import zipfile
        try:
            archive = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as exc:
            raise ValueError("Could not parse file: not a valid .xlsx workbook.") from exc
        entries = archive.infolist()
        if len(entries) > MAX_XLSX_ENTRIES:
            raise ValueError("Workbook contains too many parts to process safely.")
        if sum(entry.file_size for entry in entries) > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise ValueError("Workbook is too large once uncompressed (limit 150 MB).")
        from openpyxl import load_workbook
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.worksheets[0] if workbook.worksheets else None
            columns = sheet.max_column if sheet is not None else 0
            rows = sheet.max_row if sheet is not None else 0
            workbook.close()
        except Exception as exc:
            raise ValueError("Could not read this workbook. Check that it is a valid, unprotected Excel file.") from exc
        if columns and columns > MAX_COLS:
            raise ValueError(f"Dataset exceeds {MAX_COLS} column limit ({columns} columns found).")
        if rows and rows > MAX_ROWS + 1:
            raise ValueError(f"Dataset exceeds {MAX_ROWS:,} row limit ({rows - 1:,} rows found).")
    elif ext == "xls":
        import xlrd
        try:
            book = xlrd.open_workbook(file_contents=content, on_demand=True)
            sheet = book.sheet_by_index(0)
            columns, rows = sheet.ncols, sheet.nrows
            book.release_resources()
        except Exception as exc:
            raise ValueError("Could not read this workbook. Check that it is a valid, unprotected Excel file.") from exc
        if columns > MAX_COLS:
            raise ValueError(f"Dataset exceeds {MAX_COLS} column limit ({columns} columns found).")


# ── Sanitization ──────────────────────────────────────────────────────────────

def sanitize_string(value: Any) -> str:
    """Strip dangerous characters from any cell value before it leaves the server."""
    if value is None:
        return ""
    try:
        is_missing = pd.isna(value)
        if isinstance(is_missing, (bool, np.bool_)) and is_missing:
            return ""
    except (TypeError, ValueError):
        pass
    s = str(value)
    # Remove potential script injection
    s = re.sub(r"[<>\"'`\\]", "", s)
    return s.strip()[:500]


def sanitize_column_name(name: Any) -> str:
    s = re.sub(r"[^A-Za-z0-9_\u0600-\u06FF\s\-]", "", str(name))
    return s.strip()[:80] or "unnamed"


def _validate_json_structure(content: bytes):
    """Reject pathological nesting before handing JSON to pandas."""
    depth = 0
    in_string = False
    escaped = False
    for byte in content:
        if in_string:
            if escaped:
                escaped = False
            elif byte == ord('\\'):
                escaped = True
            elif byte == ord('"'):
                in_string = False
            continue
        if byte == ord('"'):
            in_string = True
        elif byte in (ord('{'), ord('[')):
            depth += 1
            if depth > MAX_JSON_NESTING:
                raise ValueError(f"JSON nesting exceeds {MAX_JSON_NESTING} levels.")
        elif byte in (ord('}'), ord(']')):
            depth -= 1


def _validate_dataset_shape(df: pd.DataFrame):
    if df.empty:
        raise ValueError("File parsed successfully but contains no data rows.")
    if len(df) > MAX_ROWS:
        raise ValueError(f"Dataset exceeds {MAX_ROWS:,} row limit ({len(df):,} rows found).")
    if len(df.columns) > MAX_COLS:
        raise ValueError(f"Dataset exceeds {MAX_COLS} column limit ({len(df.columns)} columns found).")
    if df.size > MAX_CELLS:
        raise ValueError(f"Dataset exceeds {MAX_CELLS:,} cell limit ({df.size:,} cells found).")


def _parse_json_dataset(content: bytes) -> pd.DataFrame:
    """Parse common JSON record uploads without materialising unbounded rows."""
    _validate_json_structure(content)
    text = content.decode('utf-8-sig')
    stripped = text.lstrip()
    if stripped.startswith('['):
        decoder = json.JSONDecoder()
        records = []
        columns = set()
        position = 1
        length = len(stripped)
        while True:
            while position < length and stripped[position].isspace():
                position += 1
            if position >= length:
                raise ValueError('JSON array is incomplete.')
            if stripped[position] == ']':
                break
            record, position = decoder.raw_decode(stripped, position)
            if not isinstance(record, dict):
                raise ValueError('JSON datasets must contain object records.')
            records.append(record)
            if len(records) > MAX_ROWS:
                raise ValueError(f"Dataset exceeds {MAX_ROWS:,} row limit ({len(records):,} rows found).")
            columns.update(record)
            if len(columns) > MAX_COLS:
                raise ValueError(f"Dataset exceeds {MAX_COLS} column limit ({len(columns)} columns found).")
            projected_cells = len(records) * len(columns)
            if projected_cells > MAX_CELLS:
                raise ValueError(f"Dataset exceeds {MAX_CELLS:,} cell limit ({projected_cells:,} cells projected).")
            while position < length and stripped[position].isspace():
                position += 1
            if position < length and stripped[position] == ',':
                position += 1
            elif position >= length or stripped[position] != ']':
                raise ValueError('JSON array is malformed.')
        if stripped[position + 1:].strip():
            raise ValueError('JSON contains trailing data.')
        return pd.DataFrame.from_records(records)

    # JSON Lines permits pandas to stop reading after the hard row boundary. Keep
    # conventional single-document JSON support for existing analyzer uploads.
    decoder = json.JSONDecoder()
    _, position = decoder.raw_decode(stripped)
    if stripped[position:].strip():
        return pd.read_json(io.BytesIO(content), lines=True, nrows=MAX_ROWS + 1)
    return pd.read_json(io.BytesIO(content))


# ── File parsing ──────────────────────────────────────────────────────────────

_ARABIC_LETTERS = re.compile(r"[؀-ۿ]")


def _decode_text(content: bytes) -> str:
    """Decode a text export: UTF-8 first, then Windows Arabic (Excel's default for Arabic CSVs)."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    for encoding in ("cp1256", "cp1252"):
        try:
            text = content.decode(encoding)
        except UnicodeDecodeError:
            continue
        if encoding == "cp1256" and not _ARABIC_LETTERS.search(text):
            continue
        return text
    return content.decode("latin-1")


def _sniff_delimiter(text: str, default: str = ",") -> str:
    """Comma, semicolon (European Excel), tab or pipe, judged from the first lines."""
    sample = "\n".join(text.splitlines()[:50])
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return default


def _read_delimited(content: bytes, sep: str | None = None) -> pd.DataFrame:
    text = _decode_text(content)
    delimiter = sep or _sniff_delimiter(text)
    # Semicolon files come from locales that also write decimals as "1,5".
    decimal = "," if delimiter == ";" else "."
    return pd.read_csv(io.StringIO(text), sep=delimiter, decimal=decimal, low_memory=False, nrows=MAX_ROWS + 1)


def parse_uploaded_file(file_obj, filename: str) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: .{ext}")

    declared_size = getattr(file_obj, "size", None)
    if declared_size is not None and declared_size > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds 20 MB limit.")
    content = file_obj.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds 20 MB limit.")
    if len(content) == 0:
        raise ValueError("Uploaded file is empty.")

    _check_spreadsheet_before_parse(content, ext)

    try:
        buffer = io.BytesIO(content)
        if ext in {"csv", "txt"}:
            df = _read_delimited(content)
        elif ext == "tsv":
            df = _read_delimited(content, sep="\t")
        elif ext in {"xlsx", "xls"}:
            df = pd.read_excel(io.BytesIO(content), engine="openpyxl" if ext == "xlsx" else "xlrd", nrows=MAX_ROWS + 1)
        elif ext in {"sav", "zsav", "por"}:
            # pyreadstat requires a filesystem path; the temporary file is deleted
            # immediately after parsing and never becomes part of the session store.
            descriptor, temporary_path = tempfile.mkstemp(suffix=f".{ext}")
            try:
                # Close the OS handle before asking pyreadstat to reopen it. This
                # is required on Windows, where an open NamedTemporaryFile may be
                # locked against the second reader.
                os.close(descriptor)
                with open(temporary_path, "wb") as temporary_file:
                    temporary_file.write(content)
                if ext == "por":
                    df, _ = pyreadstat.read_por(temporary_path, apply_value_formats=False, row_limit=MAX_ROWS + 1)
                else:
                    df, _ = pyreadstat.read_sav(temporary_path, apply_value_formats=False, row_limit=MAX_ROWS + 1)
            finally:
                if os.path.exists(temporary_path):
                    os.unlink(temporary_path)
        elif ext == "dta":
            with pd.read_stata(buffer, convert_categoricals=False, iterator=True) as reader:
                df = reader.read(MAX_ROWS + 1)
        elif ext == "json":
            df = _parse_json_dataset(content)
            _validate_dataset_shape(df)
    except ValueError as exc:
        if str(exc).startswith(("JSON", "Dataset", "File", "Workbook", "Uploaded")):
            raise  # our own validation messages are safe to show
        import logging
        logging.getLogger(__name__).warning("Analyzer could not parse %s upload: %s", ext, exc)
        raise ValueError(f"Could not read this .{ext} file. Check that it is a valid, unprotected {ext.upper()} file.") from exc
    except Exception as exc:
        # Library messages can include temp paths and internals; log them only.
        import logging
        logging.getLogger(__name__).warning("Analyzer could not parse %s upload: %s", ext, exc)
        raise ValueError(f"Could not read this .{ext} file. Check that it is a valid, unprotected {ext.upper()} file.") from exc

    _validate_dataset_shape(df)

    # Sanitize column names
    df.columns = [sanitize_column_name(c) for c in df.columns]

    # Deduplicate column names
    seen: dict[str, int] = {}
    new_cols = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df.columns = new_cols

    return df


# ── Variable type detection ───────────────────────────────────────────────────

_IDENTIFIER_PATTERN = re.compile(r"(^|[_\s])(id|patient[_\s]?id|subject[_\s]?id|respondent[_\s]?id|participant[_\s]?id|serial|record[_\s]?no|case[_\s]?no)([_\s]|$)", re.I)
# "code" names an identifier only when almost every value is unique (e.g. patient_code, not icd_code).
_CODE_PATTERN = re.compile(r"(^|[_\s])code([_\s]|$)", re.I)
# Bare row-number columns such as "respondent" or "participant" holding 1, 2, 3, ...
_SEQUENTIAL_ID_PATTERN = re.compile(r"^(respondent|participant|subject|patient|case|record|row|no|number|index|serial)s?$", re.I)
_DATE_PATTERN = re.compile(r"date|time|visit|wave|follow[_\s-]?up|year|month|day", re.I)
# Only these names make a column a time/visit role; "year_of_study" is a group, not a time axis.
_TIME_ROLE_PATTERN = re.compile(r"(^|[_\s])(date|visit|wave|timepoint|time[_\s]?point)([_\s]|$)", re.I)
_PRE_PATTERN = re.compile(r"(^|[_\s])(pre|before|baseline|t0|time0|week0|month0)([_\s]|$)", re.I)
_POST_PATTERN = re.compile(r"(^|[_\s])(post|after|follow[_\s-]?up|t1|time1|final|end|week[_\s]?\d+|month[_\s]?\d+)([_\s]|$)", re.I)
_SCALE_PATTERN = re.compile(r"^(q\d+|item[_\s]?\d+|scale|likert|agree|rating|question[_\s]?\d+|score[_\s]?\d+)|(^|_)(q|item)\d+$", re.I)
_OUTCOME_PATTERN = re.compile(
    r"outcome|result|response|endpoint|end[_\s]?point|severity|total[_\s]?score|status|event|adverse|complication|"
    r"mortality|death|died|survival|recurrence|relapse|readmi|controlled|recovered|cured|success|diagnosis|positive", re.I)
_GROUP_PATTERN = re.compile(r"group|arm|treatment|condition|intervention|cohort|exposure|category|class|allocation|year[_\s]?of[_\s]?study", re.I)
_COVARIATE_PATTERN = re.compile(r"(^|[_\s])(age|sex|gender|bmi|weight|height|income|education|ethnicity|race|smok\w*|diabet\w*|comorbid\w*)([_\s]|$)", re.I)
_PREDICTOR_PATTERN = re.compile(r"predictor|exposure|risk|factor|dose", re.I)


def _metadata(name: str, n_total: int, unique: int, missing: int, **extra) -> dict:
    """Create a consistent, reviewer-facing recognition record."""
    return {
        "unique": int(unique),
        "missing": int(missing),
        "missing_pct": round(missing / n_total * 100, 1) if n_total else 0,
        **extra,
    }


def _suggest_role(name: str, detected_type: str) -> tuple[str, float, str]:
    """Suggest a research role from a field name; never treat it as confirmed."""
    normalized = re.sub(r"[\-\s]+", "_", name.strip().lower())
    if detected_type == "id" or _IDENTIFIER_PATTERN.search(normalized):
        return "identifier", 0.98, "The field name looks like a record or participant identifier."
    if _PRE_PATTERN.search(normalized):
        return "pre_measure", 0.86, "The field name suggests a baseline or before measurement."
    if _POST_PATTERN.search(normalized):
        return "post_measure", 0.86, "The field name suggests a follow-up or after measurement."
    if detected_type == "date" or _TIME_ROLE_PATTERN.search(normalized):
        return "time", 0.84, "The field name or values suggest a time or visit variable."
    if detected_type == "likert" or _SCALE_PATTERN.search(normalized):
        return "scale_item", 0.76, "The field name looks like a questionnaire or scale item."
    # Outcome words win over group words: "bp_controlled" or "adverse_event" is what was measured.
    if _OUTCOME_PATTERN.search(normalized):
        return "outcome", 0.67, "The field name suggests a possible outcome or response."
    if _GROUP_PATTERN.search(normalized):
        return "grouping", 0.76, "The field name suggests a group, exposure, or study arm."
    if _COVARIATE_PATTERN.search(normalized):
        return "covariate", 0.6, "The field name suggests a background characteristic to describe or adjust for."
    if _PREDICTOR_PATTERN.search(normalized):
        return "predictor", 0.62, "The field name suggests a possible explanatory variable."
    return "unspecified", 0.0, "No research role can be inferred safely from the field name alone."


def _recognition_result(name: str, detected_type: str, confidence: float, n_total: int, unique: int, missing: int, warnings: list[str], **extra) -> dict:
    role, role_confidence, role_reason = _suggest_role(name, detected_type)
    return {
        "type": detected_type,
        "detected_type": detected_type,
        "confidence": confidence,
        "suggested_role": role,
        "role_confidence": role_confidence,
        "role_reason": role_reason,
        "warnings": warnings,
        **_metadata(name, n_total, unique, missing, **extra),
    }

def detect_variable_type(series: pd.Series) -> dict:
    """
    Detect variable type using heuristics.
    Returns dict with keys: type, confidence, warnings
    """
    name = str(series.name)
    n_total = len(series)
    n_missing = int(series.isna().sum())
    s = series.dropna()
    n = len(s)
    unique_vals = s.nunique()
    warnings = []

    # Unique continuous measurements are common in research data.  Treat a column as
    # an identifier only when its name carries an explicit identifier signal; using
    # uniqueness alone incorrectly hides valid outcomes such as age or scale scores.
    if _IDENTIFIER_PATTERN.search(name.strip()):
        return _recognition_result(name, "id", 0.95, n_total, unique_vals, n_missing, warnings)
    if _CODE_PATTERN.search(name.strip()) and n >= 10 and unique_vals >= 0.9 * n:
        return _recognition_result(name, "id", 0.85, n_total, unique_vals, n_missing, warnings)
    if _SEQUENTIAL_ID_PATTERN.match(name.strip()) and n >= 10 and unique_vals == n:
        numeric_ids = pd.to_numeric(s, errors="coerce")
        if numeric_ids.notna().all() and (numeric_ids % 1 == 0).all() and numeric_ids.max() - numeric_ids.min() == n - 1:
            warnings.append("Looks like a row number (1, 2, 3, ...); excluded from statistics unless you change it.")
            return _recognition_result(name, "id", 0.85, n_total, unique_vals, n_missing, warnings)

    # Date detection
    if pd.api.types.is_datetime64_any_dtype(series):
        return _recognition_result(name, "date", 0.99, n_total, unique_vals, n_missing, warnings)

    # Deliberately only infer dates from text when the name carries a date/time
    # signal.  This avoids turning free text such as "2024 cohort" into dates.
    # Numeric values such as follow_up_score=61 must never be parsed as epoch-like
    # datetimes merely because the column name mentions a visit or follow-up.
    # Infer text dates only; genuine datetime dtypes were handled above.
    is_textual_series = pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series)
    if not s.empty and is_textual_series and _DATE_PATTERN.search(name):
        parsed_dates = pd.to_datetime(s, errors="coerce", format="mixed")
        if parsed_dates.notna().mean() >= 0.85:
            return _recognition_result(name, "date", 0.88, n_total, unique_vals, n_missing, warnings)

    # Try numeric coercion
    numeric_series = pd.to_numeric(s, errors="coerce")
    is_numeric_parseable = numeric_series.notna().mean() > 0.85

    if is_numeric_parseable:
        numeric_series = numeric_series.dropna()
        unique_numeric = numeric_series.nunique()

        # Likert detection: integer-valued, 3-7 unique values, values in 1-10 range
        is_integer_like = (numeric_series % 1 == 0).all()
        val_min, val_max = float(numeric_series.min()), float(numeric_series.max())
        likert_name = _SCALE_PATTERN

        if (is_integer_like and 3 <= unique_numeric <= 7
                and 1 <= val_min and val_max <= 10
                and likert_name.match(name.strip())):
            return _recognition_result(name, "likert", 0.82, n_total, unique_numeric, n_missing, warnings,
                                       min=val_min, max=val_max)

        # Two numeric codes are more often a binary category than a continuous
        # measurement.  The researcher can override this in the review step.
        if unique_numeric == 2:
            warnings.append("Detected as binary coded categories; confirm the category labels and research role.")
            return _recognition_result(name, "categorical", 0.78, n_total, unique_numeric, n_missing, warnings,
                                       min=val_min, max=val_max, numeric_coded=True)

        # Ordinal: small number of integers
        if is_integer_like and 3 <= unique_numeric <= 10:
            warnings.append("Few ordered numeric values; confirm whether these are ranks, categories, or a scale.")
            return _recognition_result(name, "ordinal", 0.75, n_total, unique_numeric, n_missing, warnings,
                                       min=val_min, max=val_max)

        return _recognition_result(name, "numeric", 0.92, n_total, unique_numeric, n_missing, warnings,
                                   min=round(val_min, 3), max=round(val_max, 3))

    # Categorical / text
    ratio = unique_vals / max(n, 1)
    if ratio > 0.5 and unique_vals > 20:
        warnings.append("Many distinct text values; this is unlikely to be a grouping variable without recoding.")
        return _recognition_result(name, "text", 0.72, n_total, unique_vals, n_missing, warnings)

    return _recognition_result(name, "categorical", 0.88, n_total, unique_vals, n_missing, warnings,
                               top_values=s.value_counts().head(5).to_dict())


def detect_all_variables(df: pd.DataFrame) -> list[dict]:
    return [{"name": col, **detect_variable_type(df[col])} for col in df.columns]


# ── Dataset summary ───────────────────────────────────────────────────────────

def dataset_summary(df: pd.DataFrame) -> dict:
    total_cells = df.size
    missing_cells = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())

    missing_by_col = []
    for col in df.columns:
        n_miss = int(df[col].isna().sum())
        if n_miss > 0:
            missing_by_col.append({
                "column": col,
                "missing_n": n_miss,
                "missing_pct": round(n_miss / len(df) * 100, 1),
            })

    return {
        "rows": len(df),
        "cols": len(df.columns),
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_pct": round(missing_cells / total_cells * 100, 2) if total_cells else 0,
        "duplicate_rows": duplicate_rows,
        "missing_by_column": missing_by_col,
    }


# ── Preview ───────────────────────────────────────────────────────────────────

def build_preview(df: pd.DataFrame, n_rows: int = 10) -> dict:
    preview_df = df.head(n_rows).copy()
    # Sanitize all cell values before sending to client
    for col in preview_df.columns:
        preview_df[col] = preview_df[col].apply(sanitize_string)
    return {
        "columns": list(preview_df.columns),
        "rows": preview_df.values.tolist(),
    }


# ── Data preparation actions ──────────────────────────────────────────────────

MAX_SILENT_ROW_LOSS = 0.2


def apply_preparation(df: pd.DataFrame, options: dict) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Apply user-selected preparation steps. Returns (cleaned_df, change_log, warnings).

    Removing rows with missing values is limited to ``missing_columns`` when given. Without that
    list it would drop a row for a gap in any column, so it is refused when it would remove more
    than 20% of rows unless ``confirm_drop_missing`` is set: analyses already skip missing values
    for the variables they use.
    """
    log = []
    warnings = []
    df = df.copy()
    text_columns = list(df.select_dtypes(include="object").columns)

    if options.get("drop_duplicates"):
        before = len(df)
        df = df.drop_duplicates()
        removed = before - len(df)
        if removed:
            log.append(f"Removed {removed} duplicate row(s).")

    if options.get("drop_missing"):
        requested = options.get("missing_columns")
        columns = [column for column in requested if column in df.columns] if isinstance(requested, list) else list(df.columns)
        before = len(df)
        keep = df[columns].notna().all(axis=1) if columns else pd.Series(True, index=df.index)
        removed = int((~keep).sum())
        share = removed / before if before else 0
        if removed and requested is None and share > MAX_SILENT_ROW_LOSS and not options.get("confirm_drop_missing"):
            worst = df.isna().sum().sort_values(ascending=False)
            worst = ", ".join(f"{column} ({int(count)})" for column, count in worst[worst > 0].head(3).items())
            warnings.append(
                f"Rows were not removed: this would delete {removed} of {before} rows ({share:.0%}). "
                f"Most gaps are in {worst}. Each analysis already skips missing values in the variables it uses, "
                "so this step is usually unnecessary."
            )
        elif removed:
            df = df[keep]
            where = "in " + ", ".join(columns) if isinstance(requested, list) else "in any column"
            log.append(f"Removed {removed} of {before} row(s) with missing values {where}.")
            if share > MAX_SILENT_ROW_LOSS:
                warnings.append(f"{share:.0%} of rows were removed. Check that this does not bias the sample.")

    if options.get("trim_whitespace"):
        for col in text_columns:
            df[col] = df[col].astype("string").str.strip()
        log.append("Trimmed whitespace from all text columns.")

    if options.get("lowercase_categorical"):
        for col in text_columns:
            df[col] = df[col].astype("string").str.lower()
        log.append("Normalized text columns to lowercase.")

    return df, log, warnings
