import pandas as pd
from calc import calcfunc


@calcfunc(
    variables=[
        'target_year', 'residential_parking_fee_increase', 'residential_parking_fee_share_of_cars_impacted',
        'parking_utilization_reduction_per_parking_price_increase', 'parking_subsidy_for_evs'

    ],
)
def predict_parking_fee_impact(variables):
    FEES = [140, 216, 240, 264, 288, 312, 336, 360]
    SHARE_OF_CARS = [0.132, None, None, None, None, 0.126, 0.126, 0.126]
    YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021]

    CHANGE_YEAR = 2022
    CURRENT_YEAR = 2020

    target_fee = FEES[-1] * (1 + variables['residential_parking_fee_increase'] / 100)

    df = pd.DataFrame(zip(FEES, SHARE_OF_CARS), index=YEARS, columns=['ResidentialFees', 'ResidentialShareOfCarsImpacted'])

    df.loc[CHANGE_YEAR, 'ResidentialFees'] = target_fee
    df.loc[variables['target_year'], 'ResidentialFees'] = target_fee

    target_share = variables['residential_parking_fee_share_of_cars_impacted'] / 100
    df.loc[CHANGE_YEAR, 'ResidentialShareOfCarsImpacted'] = target_share
    df.loc[variables['target_year'], 'ResidentialShareOfCarsImpacted'] = target_share

    df = df.reindex(range(df.index.min(), df.index.max() + 1))

    df['ResidentialFees'] = df['ResidentialFees'].fillna(method='pad')
    df['ResidentialShareOfCarsImpacted'] = df['ResidentialShareOfCarsImpacted'].fillna(method='pad')

    pct_change = df['ResidentialFees'].pct_change().fillna(0)
    pct_change[pct_change.index < CURRENT_YEAR] = 0
    df['CarModalShareChange'] = -pct_change * 100 * .088 * df['ResidentialShareOfCarsImpacted'] / 100
    df['CarModalShareChange'] = df['CarModalShareChange'].shift(periods=1).fillna(0)
    df['CarModalShareChange'] = df['CarModalShareChange'].ewm(com=1, adjust=False).mean()

    df['ParkingSubsidyForEVs'] = 0.5 * df['ResidentialFees']
    df.loc[df.index >= CHANGE_YEAR, 'ParkingSubsidyForEVs'] = variables['parking_subsidy_for_evs']

    df['Forecast'] = False
    df.loc[df.index >= CURRENT_YEAR, 'Forecast'] = True

    return df


if __name__ == '__main__':
    #from variables import override_variable
    #with override_variable('parking_fee_share_of_cars_impacted', 30):
    df = predict_parking_fee_impact(skip_cache=True)
    print(df)
