from django.urls import path
from . import views
from .views import add_review


urlpatterns = [
    path("logout", views.logout_view, name="logout"),
    path("", views.index, name="index"),
    path("users/<int:pk>/", views.user_profile, name="profile"),
    path("edit/", views.edit_profile, name="edit_profile"),
    path("board-games/", views.manage_board_games, name="manage_board_games"),
    path("board-games/add/", views.add_board_game, name="add_board_game"),
    path("board-games/edit/<int:pk>/", views.edit_board_game, name="edit_board_game"),
    path("catalogue/", views.board_game_catalogue, name="board_game_catalogue"),
    path("boardgame/<int:pk>/", views.board_game_detail, name="board_game_detail"),
    path("boardgame/<int:pk>/borrow/", views.borrow_game, name="borrow_game"),
    path("loans/<int:pk>/return/", views.return_game, name="return_game"),
    path(
        "board-games/delete/<int:pk>/",
        views.delete_board_game,
        name="delete_board_game",
    ),
    path(
        "boardgame/<int:pk>/request/",
        views.request_borrow_game,
        name="request_borrow",
    ),
    # Collection URLs
    path("collections/", views.collection_list, name="collection_list"),
    path("collections/<int:pk>/", views.collection_detail, name="collection_detail"),
    path("collections/add/", views.add_collection, name="add_collection"),
    path("collections/<int:pk>/edit/", views.edit_collection, name="edit_collection"),
    path(
        "collections/<int:pk>/delete/",
        views.delete_collection,
        name="delete_collection",
    ),
    path(
        "collections/<int:pk>/request-access/",
        views.request_collection_access,
        name="request_collection_access",
    ),
    path("game/<int:pk>/add_review/", add_review, name="add_review"),
    path("requests/", views.manage_requests, name="manage_requests"),
    path("promote_users/", views.manage_librarians, name="manage_librarians"),
    path(
        "promote_users/<int:pk>/promote/",
        views.promote_to_librarian,
        name="promote_to_librarian",
    ),
]
