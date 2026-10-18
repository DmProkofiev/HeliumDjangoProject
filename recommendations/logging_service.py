from .models import UserInteraction

def log_interaction(request, action_type, *, publication=None, search_query=None):
    """
    Записывает одно действие пользователя в историю.

    :param request: HttpRequest (нужен для доступа к user и session)
    :param action_type: 'view' | 'like' | 'cart' | 'search'
    :param publication: объект Publication или None
    :param search_query: строка поиска (только для action_type='search')
    """
    if action_type not in dict(UserInteraction.ACTION_CHOICES):
        return None
    if action_type == 'search':
        if not search_query or len(search_query.strip()) < 2:
            return None
        search_query = search_query.strip()
    user = request.user if request.user.is_authenticated else None
    session_key = None
    if not user:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
    return UserInteraction.objects.create(
        user=user,
        session_key=session_key,
        publication=publication,
        action_type=action_type,
        search_query=search_query,
    )