import ipaddress
from django.conf import settings

def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')

def is_yookassa_request(request):
    ip_string = get_client_ip(request)
    try:
        addr = ipaddress.ip_address(ip_string)
    except ValueError:
        return False

    for net in settings.YOOKASSA_TRUSTED_NETS:
        try:
            if addr in ipaddress.ip_network(net, strict=False):
                return True
        except ValueError:
            continue
    return False