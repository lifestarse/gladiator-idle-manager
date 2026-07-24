# Build: 1
"""AdManager _AdsAndroidMixin — aggregates the android init + show mixins."""
from .adsandroidinitmixin import _AdsAndroidInitMixin
from .adsandroidshowmixin import _AdsAndroidShowMixin


class _AdsAndroidMixin(_AdsAndroidInitMixin, _AdsAndroidShowMixin):
    pass
