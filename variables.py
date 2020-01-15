import flask
from flask import session


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

    'geothermal_heat_pump_cop': 3.2,
    'geothermal_existing_building_renovation': 1.0,  # percent per year
    'geothermal_new_building_installation_share': 50,  # percent per year
    'geothermal_borehole_depth': 300,  # meters
}


def set_variable(var_name, value):
    assert var_name in VARIABLE_DEFAULTS
    assert isinstance(value, type(VARIABLE_DEFAULTS[var_name]))

    if value != VARIABLE_DEFAULTS[var_name]:
        assert flask.has_request_context()

    if value == VARIABLE_DEFAULTS[var_name]:
        if var_name in session:
            del session[var_name]
        return

    session[var_name] = value


def get_variable(var_name):
    if flask.has_request_context():
        if var_name in session:
            return session[var_name]
    return VARIABLE_DEFAULTS[var_name]
