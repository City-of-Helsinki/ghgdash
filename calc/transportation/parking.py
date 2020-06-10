import pandas as pd
from calc import calcfunc


@calcfunc(
    variables=[
        'target_year', 'parking_fee_increase', 'parking_fee_share_of_cars_impacted',
        'parking_utilization_reduction_per_parking_price_increase'
    ],
)
def predict_parking_fee_impact(variables):
    FEES = [2.0, 2.8]
    SHARE_OF_CARS = [0.15, 0.20]
    YEARS = [2011, 2017]

    CHANGE_YEAR = 2022
    CURRENT_YEAR = 2020

    target_fee = FEES[-1] * (1 + variables['parking_fee_increase'] / 100)

    df = pd.DataFrame(zip(FEES, SHARE_OF_CARS), index=YEARS, columns=['Fees', 'ShareOfCarsImpacted'])

    df.loc[CHANGE_YEAR, 'Fees'] = target_fee
    df.loc[variables['target_year'], 'Fees'] = target_fee

    target_share = variables['parking_fee_share_of_cars_impacted'] / 100
    df.loc[CHANGE_YEAR, 'ShareOfCarsImpacted'] = target_share
    df.loc[variables['target_year'], 'ShareOfCarsImpacted'] = target_share

    df = df.reindex(range(df.index.min(), df.index.max() + 1))

    df['Fees'] = df['Fees'].fillna(method='pad')
    df['ShareOfCarsImpacted'] = df['ShareOfCarsImpacted'].fillna(method='pad')

    pct_change = df['Fees'].pct_change().fillna(0)
    pct_change[pct_change.index < CURRENT_YEAR] = 0
    df['CarModalShareChange'] = -pct_change * 100 * .088 * df['ShareOfCarsImpacted'] / 100
    df['CarModalShareChange'] = df['CarModalShareChange'].shift(periods=1).fillna(0)
    df['CarModalShareChange'] = df['CarModalShareChange'].ewm(com=1, adjust=False).mean()

    df['Forecast'] = False
    df.loc[df.index >= CURRENT_YEAR, 'Forecast'] = True

    return df


if __name__ == '__main__':
    #from variables import override_variable
    #with override_variable('parking_fee_share_of_cars_impacted', 30):
    df = predict_parking_fee_impact(skip_cache=True)
    print(df)
