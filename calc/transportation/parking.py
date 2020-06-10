import pandas as pd
from calc import calcfunc


@calcfunc(
    variables=['target_year', 'parking_fee_increase'],
)
def predict_parking_fee_impact(variables):
    STARTING_FEE = 5

    index = range(2010, 2020)
    target_fee = 5 * (1 + variables['parking_fee_increase'] / 100)
    df = pd.DataFrame([STARTING_FEE] * len(index), index=index, columns=['Fees'])
    df.loc[variables['target_year']] = target_fee

    df = df.reindex(range(df.index.min(), variables['target_year'] + 1))

    df['Fees'] = df['Fees'].interpolate()

    df['CarMultiplier'] = (STARTING_FEE / df['Fees']) ** (1 / 80)

    df['Forecast'] = False
    df.loc[df.index > 2019, 'Forecast'] = True

    return df


if __name__ == '__main__':
    df = predict_parking_fee_impact(skip_cache=True)
    print(df)
