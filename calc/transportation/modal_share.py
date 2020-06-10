import pandas as pd
from calc import calcfunc
from calc.population import predict_population
from calc.transportation.datasets import prepare_transportation_emissions_dataset
from calc.transportation.parking import predict_parking_fee_impact


DATA_START_YEAR = 2015
MODAL_PASSENGER_KMS = {
    'Walking': [205697940, 278196138, 259558800, 278101968, 278101968],
    'Cycling': [204939725.5, 241588244, 211671968, 255815761.5, 255815761.5],
    'Train': [228959781, 239445434.2, 240799955.6, 236279184.7, 241841529.8],
    'Metro': [400730000, 404377386.4, 426168466.6, 557828781.4, 584138125.8],
    'Tram': [120970259.3, 123973160.3, 131807862.8, 134716581, 124330179.2],
    'Bus (Rapid)': [62023837.5, 62721205.56, 63072824.44, 47440615.07, 40685925.02],
    'Bus (IC)': [142654826, 142654826, 142654826, 142654826, 142654826],
    'Bus': [413492250, 415810312.6, 418141370.4, 363656282.8, 314066789.7],
    'Car': [2394000000, 2378988000, 2428068000, 2462400000, 2462400000],
}


@calcfunc(
    datasets=dict(
        modal_share='jyrjola/ymparistotilastot/l27_matka_kulkutapa_pks_2000_2008',
    ),
)
def prepare_daily_trips_dataset(datasets):
    df = datasets['modal_share']
    df = df[df['Alue'] == 'Koko Helsinki'].drop(columns='Alue')
    df['Vuosi'] = df['Vuosi'].astype(int)
    df = df.rename(columns=dict(Muuttuja='Variable'))
    df['Variable'] = df.Variable.map({'Määrä (matkaa)': 'Trips'})
    df = df[df['Variable'] == 'Trips'].drop(columns='Variable')
    df = df.rename(columns=dict(value='Trips', Vuosi='Year', Kulkutapa='Mode'))

    MODE_MAP = {
        'Kävely': 'Walking',
        'Polkupyörä': 'Cycling',
        'Linja-auto': 'Bus',
        'Raitiovaunu': 'Tram',
        'Juna': 'Train',
        'Metro': 'Metro',
        'Taksi': 'Taxi',
        'Henk. Auto kulj.': 'Car_Driver',
        'Henk. Auto matk.': 'Car_Passenger',
        'Muu, mikä?': 'Other',
        'Eos': 'N/A',
        'Yht': 'Total',
    }

    df['Mode'] = df['Mode'].map(MODE_MAP)
    df = df[df['Year'] > 2008]
    df = df[df['Mode'] != 'Total']
    df['Trips'] = df['Trips'].astype(int)

    df = df.set_index(['Year', 'Mode'])
    df = df.unstack('Mode')
    df.columns = df.columns.levels[1]

    # Plug in data fro 2019
    DATA_2019 = {
        'Kävely': 690016,
        'Polkupyörä': 167306,
        'Linja-auto': 222807,
        'Metro': 145541,
        'Raitiovaunu': 99995,
        'Juna': 57397,
        'Henk. Auto kulj.': 298738,
        'Henk. Auto matk.': 77435,
        'Taksi': 14463,
        'Muu, mikä?': 11394,
    }
    d = {}
    for key, val in DATA_2019.items():
        d[MODE_MAP[key]] = val
    df.loc[2019] = d

    df['Car'] = df['Car_Driver'] + df['Car_Passenger']

    df = df.drop(columns=['Car_Driver', 'Car_Passenger'])

    return df


@calcfunc(
    funcs=[
        prepare_daily_trips_dataset, predict_population, predict_parking_fee_impact
    ],
    variables=['target_year'],
)
def predict_passenger_kms(variables):
    nr_years = len(list(MODAL_PASSENGER_KMS.values())[0])
    df = pd.DataFrame(MODAL_PASSENGER_KMS, index=range(DATA_START_YEAR, DATA_START_YEAR + nr_years))
    df['Bus'] += df.pop('Bus (Rapid)') + df.pop('Bus (IC)')

    pop = predict_population()
    df['Population'] = pop['Population']
    hist_pop = df.pop('Population')

    total = df.sum(axis=1)

    kms_per_resident = total.iloc[-1] / hist_pop.iloc[-1]

    mdf = df.div(total, axis=0)

    last_hist_year = mdf.index.max()
    shares = mdf.loc[last_hist_year].to_dict()  # from last historical year

    pdf = predict_parking_fee_impact()

    TO_MODES = ['Cycling', 'Metro', 'Train', 'Tram']

    for year in range(last_hist_year + 1, variables['target_year'] + 1):
        prev = shares['Car']
        shares['Car'] += pdf.loc[year]['CarModalShareChange']
        change_per_mode = (prev - shares['Car']) / len(TO_MODES)
        for mode in TO_MODES:
            shares[mode] += change_per_mode
        mdf.loc[year] = shares

    mdf['Forecast'] = True
    mdf.loc[mdf.index <= last_hist_year, 'Forecast'] = False

    mdf['Population'] = pop['Population']

    mdf['PassengerKms'] = total
    mdf.loc[mdf.Forecast, 'PassengerKms'] = kms_per_resident * mdf['Population']

    fc = mdf.pop('Forecast')
    pop = mdf.pop('Population')
    total = mdf.pop('PassengerKms')

    mdf = mdf.mul(total, axis=0).astype(int)
    mdf['KmsPerResident'] = total / pop
    mdf['Forecast'] = fc

    return mdf


@calcfunc(
    funcs=[predict_passenger_kms, prepare_transportation_emissions_dataset]
)
def predict_road_mileage():
    edf = prepare_transportation_emissions_dataset()[['Year', 'Vehicle', 'Road', 'Mileage']]
    edf = edf.set_index('Year')

    MODE_VEHICLE_MAP = (
        ('Bus', 'Buses'),
        ('Car', 'Cars'),
    )

    df = predict_passenger_kms()

    # edf.Mileage /= 1000000
    # print(edf[edf.Vehicle == 'Cars'])
    # exit()

    # df.pop('Forecast')
    # print(df / 1000000)
    # exit()

    vehicle_km_per_passenger_km = {}
    for mode, vehicle in MODE_VEHICLE_MAP:
        mdf = edf[edf.Vehicle == vehicle][['Road', 'Mileage']]
        mdf['PassengerKms'] = df[mode]
        mdf = mdf.dropna()
        mdf['VehicleKmPerPassengerKm'] = mdf['Mileage'] / mdf['PassengerKms']

        out = mdf.groupby('Road')['VehicleKmPerPassengerKm'].mean().dropna().to_dict()
        # out = mdf[mdf.index == mdf.index.max()].set_index('Road')['VehicleKmPerPassengerKm'].to_dict()
        vehicle_km_per_passenger_km[vehicle] = out

    last_hist_year = edf.index.max()
    edf = edf.reset_index().set_index(['Year', 'Vehicle', 'Road']).unstack(['Vehicle', 'Road'])
    edf.columns = edf.columns.droplevel()

    edf = edf.reindex(range(edf.index.min(), df.index.max() + 1))

    for mode, vehicle in MODE_VEHICLE_MAP:
        for road_type, per_trip in vehicle_km_per_passenger_km[vehicle].items():
            out = df.loc[df.index > last_hist_year, mode] * per_trip
            edf.loc[edf.index > last_hist_year, (vehicle, road_type)] = out

    edf.columns = edf.columns.to_list()

    edf['Forecast'] = False
    edf.loc[edf.index > last_hist_year, 'Forecast'] = True

    return edf


if __name__ == '__main__':
    pd.set_option('display.max_rows', None)
    """
    df = predict_road_mileage(skip_cache=True)
    fc = df.pop('Forecast')
    df /= 1000000
    df['Forecast'] = fc
    print(df)
    """
    from calc.transportation.cars import predict_cars_emissions
    from variables import override_variable

    with override_variable('parking_fee_share_of_cars_impacted', 0):
        print('override')
        print(predict_road_mileage()[[('Cars', 'Highways'), ('Cars', 'Urban')]])
        print(predict_cars_emissions()[['Mileage', 'Emissions']])

    print('no override')
    print(predict_road_mileage()[[('Cars', 'Highways'), ('Cars', 'Urban')]])
    print(predict_cars_emissions()[['Mileage', 'Emissions']])

    #print(df)
    #df = predict_road_mileage()
    #print(df)
