from django.shortcuts import redirect


class BlockAdminMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        current_path = request.path

        restricted_urls = [
            "/",
            "/collections/",
            "/games/",
            "/profile/",
            "/borrow/",
            "/reviews/",
        ]

        if current_path.startswith("/admin/"):
            return self.get_response(request)

        if request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
        ):
            current_path = request.path
            if any(current_path.startswith(url) for url in restricted_urls):
                return redirect("admin:index")  # Redirect to admin interface

        response = self.get_response(request)
        return response
