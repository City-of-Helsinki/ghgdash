import pandas as pd

from utils.colors import GHG_MAIN_SECTOR_COLORS
from utils.data import get_contributions_from_multipliers
from common.locale import lazy_gettext as _

from . import calcfunc
from .district_heating import predict_district_heating_emissions
from .electricity import predict_electricity_consumption_emissions
from .geothermal import predict_geothermal_production
from .transportation.cars import predict_cars_emissions

SECTORS = {
    'BuildingHeating': dict(
        name='Rakennusten lämmitys',
        name_en='Building heating',
        improvement_name='Rakennusten lämmityksen aiheuttamien päästöjen väheneminen',
        improvement_name_en='Emission reductions from heating of buildings',
        subsectors={
            'DistrictHeat': dict(
                name='Kaukolämpö',
                name_en='District heating',
                subsectors={
                    'DistrictHeatProduction': dict(
                        name='Kaukolämmön tuotanto',
                        name_en='District heat production',
                        improvement_name='Kaukolämmön tuotannon puhdistuminen',
                        improvement_name_en='Lower emissions from district heat production'
                    ),
                    'DistrictHeatDemand': dict(
                        name='Kaukolämmön kulutus',
                        name_en='District heat consumption',
                        improvement_name='Rakennusten energiatehokkuuden parantuminen',
                        improvement_name_en='Improvement in building heat use efficiency'
                    ),
                    'DistrictHeatToGeothermalProduction': dict(
                        name='Kaukolämmön korvaaminen maalämmöllä',
                        name_en='Replacing district heat with geothermal',
                    ),
                },
                improvement_name='Kaukolämmön kulutuksen väheneminen ja tuotannon puhdistuminen',
                improvement_name_en='Reduction of district heat consumption and cleaner production',
            ),
            'OilHeating': dict(
                name='Öljylämmitys',
                name_en='Oil heating',
                improvement_name='Öljyn osuuden vähentäminen erillislämmityksessä',
                improvement_name_en='Decreasing use of oil in building heating',
            ),
            'ElectricityHeating': dict(
                name='Sähkölämmitys',
                name_en='Electric heating',
                improvement_name='Sähkölämmityksen aiheuttamien päästöjen väheneminen',
                improvement_name_en='Decrease in emissions from electricity-based heating',
            ),
            'GeothermalHeating': dict(
                name='Maalämpö',
                name_en='Geothermal',
            ),
        }
    ),
    'Transportation': dict(
        name='Liikenne',
        name_en='Transportation',
        improvement_name='Liikenteen päästöjen väheneminen',
        subsectors={'Cars': dict(
            name='Henkilöautot',
            name_en='Cars',
            improvement_name='Henkilöautoliikenteen päästöjen väheneminen',
            subsectors={
                'CarFleet': dict(
                    name='Ajoneuvoteknologia',
                    name_en='Vehicle technology',
                    improvement_name='Sähköautojen osuuden kasvu',
                    improvement_name_en='Increase in the share of EVs',
                ),
                'CarMileage': dict(
                    name='Henkilöautoilusuorite',
                    name_en='Car mileage',
                    improvement_name='Henkilöautoilusuoritteen pieneneminen',
                    improvement_name_en='Reduction in net car mileage',
                ),
            }),
            'Trucks': dict(
                name='Kuorma-autot',
                improvement_name='Kuorma-autoliikenteen päästöjen väheneminen',
                improvement_name_en='Reduction in emissions from truck traffic',
                name_en='Trucks',
            ),
            'OtherTransportation': dict(
                name='Muu liikenne',
                improvement_name='Muun liikenteen päästöjen väheneminen',
                improvement_name_en='Reduction in emissions from other traffic',
                name_en='Other transportation',
            ),
        }
    ),
    'ElectricityConsumption': dict(
        name='Kulutussähkö',
        name_en='Electricity consumption',
        improvement_name='Kulutussähkön aiheuttamien päästöjen väheneminen',
        improvement_name_en='Reduction in emissions from electricity consumption',
        subsectors={
            'SolarProduction': dict(
                name='Aurinkosähkö',
                name_en='PV production',
                improvement_name='Paikallisesti tuotetun sähkön osuuden lisääminen',
                improvement_name_en='Increasing the amount of local PV energy production',
            ),
            'ElectricityDemand': dict(
                name='Kulutussähkön kysyntä',
                name_en='Electricity demand',
                improvement_name='Kulutussähkön määrän vähentäminen',
                improvement_name_en='Reducing electricity consumption',
            ),
            'ElectricityProduction': dict(
                name='Sähköntuotanto',
                name_en='Electricity production',
                improvement_name='Valtakunnallisen sähköntuotannon puhdistuminen',
                improvement_name_en='Decrease in the national electricity production emission factor',
            )
        }
    ),
    'Waste': dict(
        name='Jätteiden käsittely',
        name_en='Waste management',
        improvement_name='Jätteiden käsittelyn päästöjen väheneminen',
    ),
    'Industry': dict(
        name='Teollisuus ja työkoneet',
        name_en='Industry',
        improvement_name='Teollisuuden ja työkoneiden päästöjen väheneminen',
    ),
    'Agriculture': dict(
        name='Maatalous',
        name_en='Agriculture',
        improvement_name='Maatalouspäästöjen väheneminen',
    ),
}
for key, val in SECTORS.items():
    if 'subsectors' not in val:
        val['subsectors'] = {}
    val['color'] = GHG_MAIN_SECTOR_COLORS[key]


TARGETS = {
    ('BuildingHeating', 'DistrictHeat'): (754.589056908339, 250.733198734865),
    ('BuildingHeating', 'OilHeating'): (16.1569293157852, 0.0),
    ('BuildingHeating', 'ElectricityHeating'): (51.0638673954148, 29.7160855925585),
    ('BuildingHeating', 'GeothermalHeating'): (0, 0),
    ('ElectricityConsumption', ''): (242.663770299608, 150.979312657901),
    # ('Liikenne', 262.55592574098, 229.655246625791),
    ('Transportation', 'Cars'): (128, 118.98),
    ('Transportation', 'Trucks'): (60, 49.47),
    ('Transportation', 'OtherTransportation'): (74.55, 61.2),
    ('Industry', ''): (3.23358058861613, 2.62034901128448),
    ('Waste', ''): (60.5886441012345, 50.6492489473935),
    ('Agriculture', ''): (0.637983301315191, 0.55519935555745),
}


def get_sector_by_path(path):
    if isinstance(path, str):
        path = tuple([path])

    next_metadata = SECTORS
    for sp in path:
        if not sp:
            continue
        metadata = next_metadata[sp]
        next_metadata = metadata.get('subsectors', {})
    return metadata


@calcfunc(
    datasets=dict(
        ghg_emissions='jyrjola/hsy/pks_khk_paastot',
    ),
)
def prepare_emissions_dataset(datasets) -> pd.DataFrame:
    df = datasets['ghg_emissions']
    df = df[df.Kaupunki == 'Helsinki'].drop(columns='Kaupunki')
    df = df.set_index('Vuosi').copy()
    df = df.reset_index().groupby(['Vuosi', 'Sektori1', 'Sektori2', 'Sektori3'])['Päästöt'].sum().reset_index()

    df = df.rename(columns=dict(
        Sektori1='Sector1', Sektori2='Sector2', Sektori3='Sector3', Päästöt='Emissions', Vuosi='Year'
    ))

    sec1_renames = {val['name']: key for key, val in SECTORS.items()}
    sec1_renames['Lämmitys'] = 'BuildingHeating'
    sec1_renames['Sähkö'] = 'ElectricityConsumption'
    df['Sector1'] = df['Sector1'].map(lambda x: sec1_renames[x])

    sec2_renames = {}
    for sector in SECTORS.values():
        sec2_renames.update({val['name']: key for key, val in sector['subsectors'].items()})
    df['Sector2'] = df['Sector2'].map(lambda x: sec2_renames.get(x, ''))
    df['Sector3'] = df['Sector3'].map(lambda x: sec2_renames.get(x, ''))

    # Move transportation sectors one hierarchy level up
    df.loc[df.Sector1 == 'Transportation', 'Sector2'] = df['Sector3']

    df = df.groupby(['Year', 'Sector1', 'Sector2']).sum().reset_index()
    df.loc[(df.Sector1 == 'Transportation') & (df.Sector2 == ''), 'Sector2'] = 'OtherTransportation'
    df['Sector'] = list(zip(df.Sector1, df.Sector2))
    df = df.drop(columns=['Sector1', 'Sector2'])

    df = df.pivot(index='Year', columns='Sector', values='Emissions')

    df.columns = pd.MultiIndex.from_tuples(df.columns)
    return df


@calcfunc(
    variables=['target_year'],
    datasets=dict(),
    funcs=[
        prepare_emissions_dataset, predict_district_heating_emissions,
        predict_electricity_consumption_emissions,
        predict_cars_emissions, predict_geothermal_production,
    ],
)
def predict_emissions(variables, datasets):
    df = prepare_emissions_dataset()
    last_historical_year = df.index.max()

    for year in range(df.index.max() + 1, variables['target_year'] + 1):
        df.loc[year] = None

    subsector_map = {}
    for sec_name, sector in SECTORS.items():
        for subsector_name, subsector in sector['subsectors'].items():
            subsector_map[subsector_name] = dict(supersector=sec_name)

    """
    target_map = {}
    for key, val in TARGETS.items():
        if key in SECTORS:
            key = (key, None)
        else:
            key = (subsector_map[key]['supersector'], key)
        target_map[key] = val
    """

    df.loc[2030] = [TARGETS[key][0] for key in df.columns]
    df.loc[2035] = [TARGETS[key][1] for key in df.columns]
    df = df.interpolate()

    pdf = predict_district_heating_emissions()
    df.loc[df.index > last_historical_year, ('BuildingHeating', 'DistrictHeat')] = \
        pdf.loc[pdf.index > last_historical_year, 'NetEmissions']

    pdf = predict_electricity_consumption_emissions()
    df.loc[df.index > last_historical_year, ('ElectricityConsumption', '')] = \
        pdf.loc[pdf.index > last_historical_year, 'NetEmissions']

    pdf = predict_geothermal_production()
    df.loc[df.index > last_historical_year, ('BuildingHeating', 'GeothermalHeating')] = \
        pdf.loc[pdf.index > last_historical_year, 'Emissions']

    df[('ElectricityConsumption', 'SolarProduction')] = None

    pdf = predict_cars_emissions()
    df.loc[df.index > last_historical_year, ('Transportation', 'Cars')] = \
        pdf.loc[pdf.index > last_historical_year, 'Emissions']

    # FIXME: Plug other emission prediction models

    df['Forecast'] = False
    df.loc[df.index > last_historical_year, 'Forecast'] = True

    return df


def calculate_district_heating_reductions(rdf, df):
    perc = get_contributions_from_multipliers(df, 'NetHeatDemand', 'Emission factor', ['GeothermalProduction'])
    out = pd.DataFrame(index=rdf.index)
    out['DistrictHeatDemand'] = rdf * perc.NetHeatDemand
    out['DistrictHeatProduction'] = rdf * perc['Emission factor']
    out['DistrictHeatToGeothermalProduction'] = rdf * perc['GeothermalProduction']
    out['DistrictHeatDemand'] -= out['DistrictHeatToGeothermalProduction']
    return out


def calculate_cars_reductions(rdf, df):
    perc = get_contributions_from_multipliers(df, 'Mileage', 'EmissionFactor')
    out = pd.DataFrame(index=rdf.index)
    out['CarFleet'] = rdf * perc.EmissionFactor
    out['CarMileage'] = rdf * perc['Mileage']
    return out


def calculate_electricity_consumption_reductions(rdf, df):
    perc = get_contributions_from_multipliers(df, 'NetConsumption', 'EmissionFactor', ['SolarProduction'])
    out = pd.DataFrame(index=rdf.index)
    ed = out['ElectricityDemand'] = rdf * perc.NetConsumption
    out['ElectricityProduction'] = rdf * perc.EmissionFactor
    out['SolarProduction'] = rdf * perc.SolarProduction
    out['ElectricityDemand'] -= out['SolarProduction']
    return out


@calcfunc(
    funcs=[
        predict_emissions,
        predict_district_heating_emissions,
        predict_cars_emissions,
        predict_electricity_consumption_emissions,
    ],
)
def predict_emission_reductions():
    df = predict_emissions()
    last_hist_year = df.loc[~df.Forecast].index.max()

    df = df.loc[df.index >= last_hist_year].drop(columns='Forecast', level=0)
    # Calculate emission reductions from the predicted emissions
    df = -(df - df.iloc[0])
    df = df.iloc[1:]

    new_cols = [(*x, '') for x in df.columns.to_flat_index()]
    df.columns = pd.MultiIndex.from_tuples(new_cols, names=['Sector1', 'Sector2', 'Sector3'])

    pdf = predict_district_heating_emissions()
    shares = calculate_district_heating_reductions(df['BuildingHeating']['DistrictHeat'], pdf)
    col_names = [('BuildingHeating', 'DistrictHeat', str(x)) for x in shares.columns]
    df[col_names] = shares
    df = df.drop(columns=('BuildingHeating', 'DistrictHeat', ''))

    pdf = predict_cars_emissions()
    shares = calculate_cars_reductions(df['Transportation']['Cars'], pdf)
    col_names = [('Transportation', 'Cars', str(x)) for x in shares.columns]
    df[col_names] = shares
    df = df.drop(columns=('Transportation', 'Cars', ''))

    pdf = predict_electricity_consumption_emissions()
    shares = calculate_electricity_consumption_reductions(df['ElectricityConsumption'][''], pdf)
    col_names = [('ElectricityConsumption', str(x), '') for x in shares.columns]

    df = df.drop(columns='ElectricityConsumption', level=0)
    df[col_names] = shares

    df = df.sort_index(axis=1)

    return df


if __name__ == '__main__':
    pd.set_option('display.max_rows', None)
    df = predict_emission_reductions()
    #print(df.columns)
    print(df)
