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
    YEARS = [2011, 2017]
    CHANGE_YEAR = 2022
    CURRENT_YEAR = 2020
    SHARE_OF_CARS = 0.15

    target_fee = FEES[-1] * (1 + variables['parking_fee_increase'] / 100)

    df = pd.DataFrame(FEES, index=YEARS, columns=['Fees'])

    df.loc[CHANGE_YEAR, 'Fees'] = target_fee
    df.loc[variables['target_year'], 'Fees'] = target_fee

    df['ShareOfCarsImpacted'] = SHARE_OF_CARS
    target_share = variables['parking_fee_share_of_cars_impacted'] / 100
    df.loc[CHANGE_YEAR, 'ShareOfCarsImpacted'] = target_share
    df.loc[variables['target_year'], 'ShareOfCarsImpacted'] = target_share

    df = df.reindex(range(df.index.min(), df.index.max() + 1))

    df['Fees'] = df['Fees'].fillna(method='pad')
    df['ShareOfCarsImpacted'] = df['ShareOfCarsImpacted'].fillna(method='pad')

    pct_change = df['Fees'].pct_change().fillna(0)

    df['CarModalShareChange'] = -pct_change * 100 * .088 * df['ShareOfCarsImpacted'] / 100
    df['CarModalShareChange'] = df['CarModalShareChange'].shift(periods=1).fillna(0)
    df['CarModalShareChange'] = df['CarModalShareChange'].ewm(com=1, adjust=False).mean()

    df['Forecast'] = False
    df.loc[df.index >= CURRENT_YEAR, 'Forecast'] = True

    return df


if __name__ == '__main__':
    df = predict_parking_fee_impact(skip_cache=True)
    print(df)
