from .common import *
from accounts.identity import find_user_by_identifier, normalize_email
from accounts.security import login_allowed, login_succeeded

@require_POST
def login_api(request):
    data = get_payload(request)
    username = normalize_email(str(data.get('username') or data.get('email') or '')[:150])
    password = data.get('password', '')
    if not isinstance(password, str) or len(password) > 1024:
        return JsonResponse({'success': False, 'error': 'Invalid username or password.'}, status=400)
    if not login_allowed(request, 'dashboard-login', username):
        log_activity(request, 'auth', 'system', 'Dashboard login rate limit reached', metadata={'username': username[:150]})
        return JsonResponse({'success': False, 'error': 'Too many sign-in attempts. Please wait before trying again.'}, status=429)
    # Phone keyboards often capitalise the first character of a username. Find
    # the stored username/email without case sensitivity, then let Django
    # perform the normal password validation through its auth backend.
    matched_user = find_user_by_identifier(username)
    authentication_username = matched_user.username if matched_user else username
    user = authenticate(request, username=authentication_username, password=password)
    if not user:
        log_activity(request, 'auth', 'system', 'Failed dashboard sign-in', metadata={'username': username[:150]})
        return JsonResponse({'success': False, 'error': 'Invalid username or password.'}, status=401)
    if not has_dashboard_access(user):
        log_activity(request, 'auth', 'system', 'Dashboard sign-in rejected: no access', user)
        return JsonResponse({'success': False, 'error': 'This account does not have dashboard access.'}, status=403)
    login(request, user)
    login_succeeded(request, 'dashboard-login', username)
    log_activity(request, 'auth', 'login', 'Signed in to dashboard', user)
    return JsonResponse({'success': True, 'user': user_to_dict(user)})

@require_POST
def logout_api(request):
    log_activity(request, 'auth', 'system', 'Signed out of dashboard')
    logout(request)
    return JsonResponse({'success': True})

@require_GET
@api_permission_required('dashboard.view')
def me_api(request):
    return JsonResponse({
        'user': user_to_dict(request.user),
        'role': get_dashboard_role(request.user),
        'permissions': permissions_for_user(request.user),
        'modules': module_registry_for_user(request.user),
    })
