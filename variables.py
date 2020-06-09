import json
import flask
import hashlib
from flask import session
from contextlib import contextmanager


SCHEMA = {
    "definitions": {
        "goal": {
            "type": "object",
            "properties": {
                "year": {"type": "number"},
                "value": {"type": "value"},
            },
            "required": ["year", "value"],
        },
    }
}


# Variables
VARIABLE_DEFAULTS = {
    'target_year': 2035,
    'population_forecast_correction': 0,  # Percent in target year
    'ghg_reductions_reference_year': 1990,
    'ghg_reductions_percentage_in_target_year': 80,
    'building_area_owned_by_org': 19,  # percent of all area
    'ghg_emission_targets': [
        {
            'year': 2030,
            'Kaukolämpö': 755,
            'Öljylämmitys': 16,
            'Sähkölämmitys': 51,
            'Kulutussähkö': 243,
            'Liikenne': 263,
            'Teollisuus ja työkoneet': 3,
            'Jätteiden käsittely': 61,
            'Maatalous': 1,
        }, {
            'year': 2035,
            'Kaukolämpö': 251,
            'Öljylämmitys': 0,
            'Sähkölämmitys': 30,
            'Kulutussähkö': 151,
            'Liikenne': 230,
            'Teollisuus ja työkoneet': 3,
            'Jätteiden käsittely': 51,
            'Maatalous': 1,
        }
    ],

    'road_transportation_mileage_forecast': [
        ('Cars', 'Highways', 833.66),
        ('Cars', 'Urban', 1040.0),
        ('Trucks', 'Highways', 35.92 + 31.89),  # trailer + no-trailer
        ('Trucks', 'Urban', 29.42 + 28.44),
        ('Vans', 'Highways', 3.17),
        ('Vans', 'Urban', 2.97),
        ('Buses', 'Urban', 42.81),
        ('Buses', 'Highways', 6.31),
        # ('jkl', 'ratikka', 12.21),
        # ('jkl', 'juna', 4.97),
        # ('jkl', 'metro', 5.41)
    ],
    'road_transportation_emission_factor_forecast': [
        ('Cars', 104.29),
        ('Vans', 136.58),
        ('Trucks', 393.68),
        ('Buses:Local', 55.8),
        ('Buses:Other', 557.97)
    ],


    'bio_emission_factor': 0,  # In percents

    'municipality_name': 'Helsinki',
    'org_genitive': 'Helsingin kaupunkikonsernin',
    'org_nominative': 'Helsingin kaupunkikonserni',
    'municipality_genitive': 'Helsingin',
    'municipality_locative': 'Helsingissä',

    'district_heating_operator': '005',  # Helen Oy
    'district_heating_target_production_ratios': {
        'Lämpöpumput': 33,
        'Puupelletit ja -briketit': 33,
        'Maakaasu': 34,
        'Kivihiili ja antrasiitti': 0
    },
    'district_heating_target_demand_change': 0,

    'district_heating_existing_building_efficiency_change': -2.0,  # Percent per year
    'district_heating_new_building_efficiency_change': -2.5,  # Percent per year
    'district_heating_heat_pump_cop': 4.0,

    'electricity_production_emissions_correction': 0,
    'electricity_consumption_per_capita_adjustment': -2.0,  # Percent per year

    'solar_power_existing_buildings_percentage': 75,
    'solar_power_new_buildings_percentage': 90,
    'yearly_pv_energy_production_kwh_wp': 0.9,         # kWh/Wp in a year

    'cars_bev_percentage': 60,
    'cars_mileage_per_resident_adjustment': -30,
    'vehicle_fuel_bio_percentage': 30,
    'parking_fee_increase': 50,

    'geothermal_heat_pump_cop': 3.2,
    'geothermal_existing_building_renovation': 1.0,  # percent per year
    'geothermal_new_building_installation_share': 50,  # percent per year
    'geothermal_borehole_depth': 300,  # meters
}


_variable_overrides = {}

# Make a hash of the default variables so that when they change,
# we will reset everybody's custom session variables.
DEFAULT_VARIABLE_HASH = hashlib.md5(json.dumps(VARIABLE_DEFAULTS).encode('utf8')).hexdigest()

_allow_variable_set = False


def set_variable(var_name, value):
    assert var_name in VARIABLE_DEFAULTS
    assert isinstance(value, type(VARIABLE_DEFAULTS[var_name]))

    if not flask.has_request_context():
        if not _allow_variable_set:
            raise Exception('Should not set variable outside of request context')
        _variable_overrides[var_name] = value
        return

    if value == VARIABLE_DEFAULTS[var_name]:
        if var_name in session:
            del session[var_name]
        return

    session[var_name] = value


def get_variable(var_name, var_store=None):
    out = None

    if var_store is not None:
        out = var_store.get(var_name)
    elif flask.has_request_context():
        if session.get('default_variable_hash', '') != DEFAULT_VARIABLE_HASH:
            reset_variables()
        if var_name in session:
            out = session[var_name]
    elif var_name in _variable_overrides:
        out = _variable_overrides[var_name]

    if out is None:
        out = VARIABLE_DEFAULTS[var_name]

    if isinstance(out, list):
        # Make a copy
        return list(out)

    return out


def reset_variable(var_name):
    if flask.has_request_context():
        if var_name in session:
            del session[var_name]
    else:
        if var_name in _variable_overrides:
            del _variable_overrides[var_name]


def reset_variables():
    if flask.has_request_context():
        session['default_variable_hash'] = DEFAULT_VARIABLE_HASH
        for var_name in VARIABLE_DEFAULTS.keys():
            if var_name not in session:
                continue
            del session[var_name]
    else:
        _variable_overrides.clear()


def copy_variables():
    out = {}
    for var_name in VARIABLE_DEFAULTS.keys():
        out[var_name] = get_variable(var_name)
    return out


@contextmanager
def allow_set_variable():
    global _allow_variable_set

    old = _allow_variable_set
    _allow_variable_set = True
    try:
        yield None
    finally:
        _allow_variable_set = old
