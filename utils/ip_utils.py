def get_client_ip(request):
    """Extract the client IP from request headers."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip_list = x_forwarded_for.split(",")
        # Return the real IP (considering the first IP if there are multiple IPs)
        return ip_list[0].strip()
    return request.META.get("REMOTE_ADDR")


def get_device_type(request):
        user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
        if "mobile" in user_agent:
            return "mobile"
        elif "tablet" in user_agent:
            return "tablet"
        return "desktop"