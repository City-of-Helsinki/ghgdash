import os
import requests
from calc.emissions import predict_emission_reductions, get_sector_by_path


APLANS_API_URL = os.getenv('APLANS_API_URL', 'https://aplans.api.hel.ninja/v1')
APLANS_API_TOKEN = os.getenv('APLANS_API_TOKEN')
APLANS_PLAN_IDENTIFIER = os.getenv('APLANS_PLAN_IDENTIFIER', 'hnh2035')


def api_get(resource, params={}):
    resp = requests.get('%s/%s/' % (APLANS_API_URL, resource), params=params)
    resp.raise_for_status()
    return resp.json()


def _get_headers():
    auth = 'Token %s' % APLANS_API_TOKEN
    headers = {
        'Authorization': auth,
        'Accept-Language': 'fi',
    }
    return headers


def api_post(resource, data):
    resp = requests.post('%s/%s/' % (APLANS_API_URL, resource), json=data, headers=_get_headers())
    if resp.status_code == 400:
        raise Exception('API POST: %s' % str(resp.json()))
    resp.raise_for_status()
    return resp.json()


def api_delete(resource, obj_id):
    resp = requests.delete('%s/%s/%s/' % (APLANS_API_URL, resource, obj_id), headers=_get_headers())
    if resp.status_code == 400:
        raise Exception('API DELETE: %s' % str(resp.json()))
    resp.raise_for_status()


def api_put(resource, obj_id, data):
    resp = requests.put('%s/%s/%s/' % (APLANS_API_URL, resource, obj_id), json=data, headers=_get_headers())
    if resp.status_code == 400:
        raise Exception('API PUT: %s' % str(resp.json()))
    resp.raise_for_status()
    return resp.json()


def find_plan(identifier):
    ret = api_get('plan', dict(identifier=identifier))
    res = ret.get('results', [])
    assert len(res) == 1, 'Plan %s not found' % identifier
    return res[0]


SECTOR_MAP = {
    'DistrictHeatProduction': dict(
        name='Helenin toimet',
    ),
    'DistrictHeatDemand': dict(
        components=[
            dict(name='Lämmön kokonaiskulutuksen vähentäminen', weight=13, identifier='DistrictHeatDemand'),
            dict(name='Lämmön kysyntäjouston lisääminen', identifier='DistrictHeatDemandElasticity', weight=2),
            dict(name='Hyödyntämättömän hukkalämmön talteenotto', identifier='WasteHeatRecovery', weight=1),
        ]
    ),
    'DistrictHeatToGeothermalProduction': dict(
        name='Paikallisesti tuotetun lämmön osuuden lisääminen'
    ),
    'SolarProduction': dict(
        name='Paikallisesti tuotetun sähkön osuuden lisääminen'
    ),
    'CarFleet': dict(
        name='Sähköautojen osuuden kasvu'
    ),
    'Trucks': dict(
        name='Raskaan liikenteen teknologia'
    ),
    'CarMileage': dict(components=[
        dict(
            name='Joukkoliikenteen kulkumuoto-osuuden nosto',
            identifier='PublicTransportShare'
        ),
        dict(
            name='Pysäköintimaksujen korotus',
            identifier='ParkingPrice'
        ),
        dict(
            name='Uudet liikkumispalvelut',
            identifier='CarSharing',
        ),
    ]),
    'OtherTransportation': dict(components=[
        dict(name='Sataman päästöjen vähennys', identifier='Harbor'),
        dict(name='Ajoneuvoliikenteen hinnoittelujärjestelmä', identifier='CarTrafficCost'),
        dict(
            name='Jalankulun ja pyöräliikenteen kulkumuoto-osuuden nosto',
            identifier='PedestrianShare',
        ),
        dict(
            name='Tiivistyvä maankäyttö',
            identifier='UrbanDensity',
        ),
    ]),
    'ElectricityDemand': dict(components=[
        dict(name='Kulutussähkön määrän vähentäminen', identifier='ElectricityDemand', weight=2),
        dict(name='Sähkön kysyntäjouston lisääminen', identifier='ElectricityDemandElasticity', weight=1),
    ]),
    'Agriculture': dict(skip=True),
    'Industry': dict(skip=True),
    'Waste': dict(skip=True),
}


def get_reduction_sectors():
    df = predict_emission_reductions()
    df.columns = df.columns.to_flat_index()
    last_year = df.iloc[-1].sort_values(ascending=False)
    last_year = last_year[last_year > 0]

    last_year = last_year[~last_year.index.isin([
        ('ElectricityConsumption', 'ElectricityProduction', '')
    ])]

    out = []

    for sector_path, weight in last_year.items():
        sector = get_sector_by_path(sector_path)
        identifier = [x for x in sector_path if x][-1]
        name = sector.get('improvement_name') or sector['name']
        if identifier in SECTOR_MAP:
            if SECTOR_MAP[identifier].get('skip'):
                continue
            comps = SECTOR_MAP[identifier].get('components')
            if comps:
                cweights = sum([c.get('weight', 1) for c in comps])
                for c in comps:
                    out.append(dict(
                        identifier=c['identifier'],
                        name=c['name'],
                        weight=c.get('weight', 1) / cweights * weight
                    ))
                continue
            else:
                name = SECTOR_MAP[identifier]['name']
        out.append(dict(identifier=identifier, name=name, weight=weight))

    from pprint import pprint

    print(last_year * 100 / last_year.sum())
    red_sum = sum([x['weight'] for x in out])
    for x in out:
        x['weight'] = x['weight'] * 100 / red_sum

    out = sorted(out, key=lambda x: x['weight'], reverse=True)
    pprint(out)
    return out


def doit():
    sectors = get_reduction_sectors()
    plan = find_plan(APLANS_PLAN_IDENTIFIER)
    res = api_get('impact_group', params=dict(plan__identifier=APLANS_PLAN_IDENTIFIER))
    groups_by_id = {x['identifier']: x for x in res['results']}
    for sector in sectors:
        sector['plan'] = plan['url']
        sector['parent'] = None
        old = groups_by_id.get(sector['identifier'])
        if old:
            api_put('impact_group', old['id'], sector)
            old['found'] = True
        else:
            api_post('impact_group', sector)

    for old in groups_by_id.values():
        found = old.get('found')
        if not found:
            #api_delete('impact_group', old['id'])
            raise Exception('Extra impact group: %s' % old['identifier'])
    print('all done')


doit()
