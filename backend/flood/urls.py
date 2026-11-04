from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views
router = DefaultRouter(); router.register("stations", views.StationViewSet)
urlpatterns = router.urls + [
    path("forecast/<int:pk>/", views.forecast), path("predict/", views.what_if),
    path("replay/events/<int:pk>/", views.replay_events), path("replay/<int:pk>/", views.replay),
    path("alerts/", views.AlertList.as_view()), path("subscribe/", views.Subscribe.as_view()),
]
