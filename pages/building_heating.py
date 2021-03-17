from .main_sector_base import MainSectorPage
from common.locale import lazy_gettext as _


class BuildingHeatingPage(MainSectorPage):
    id = 'building-heating'
    path = '/rakennusten-lammitys'
    emission_sector = ('BuildingHeating',)
    emission_name = _('Heating emissions')
