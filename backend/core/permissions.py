"""Dashboard access decorators for function-based JSON views."""

from functools import wraps

from django.http import JsonResponse

from dashboard.permissions import has_dashboard_access, has_dashboard_permission, is_super_admin


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Please log in to open the dashboard.'}, status=401)
        if not has_dashboard_access(request.user):
            return JsonResponse({'success': False, 'error': 'Dashboard access is required.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def api_permission_required(permission):
    def decorator(view):
        @api_login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_dashboard_permission(request.user, permission):
                return JsonResponse({'success': False, 'error': f'Missing dashboard permission: {permission}'}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def api_super_admin_required(view):
    @api_login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_super_admin(request.user):
            return JsonResponse({'success': False, 'error': 'Only a Super Admin can do this.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def api_save_permission_required(module):
    """For a ``save`` view that creates without ``pk`` and edits with one:
    requires ``<module>.create`` or ``<module>.edit`` accordingly."""
    def decorator(view):
        @api_login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            permission = f"{module}.{'edit' if kwargs.get('pk') is not None else 'create'}"
            if not has_dashboard_permission(request.user, permission):
                return JsonResponse({'success': False, 'error': f'Missing dashboard permission: {permission}'}, status=403)
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
