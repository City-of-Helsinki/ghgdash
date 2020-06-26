from common.locale import lazy_gettext as _
from .main_sector_base import MainSectorPage


class TransportationPage(MainSectorPage):
    id = 'transportation'
    path = '/liikenne'
    emission_sector = ('Transportation',)
    emission_name = _('Transportation emissions')
    is_main_page = True
