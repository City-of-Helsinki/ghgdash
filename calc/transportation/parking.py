import pandas as pd
from calc import calcfunc


@calcfunc(
    variables=['target_year'],
)
def predict_parking_fees(variables):
    index = list(range(2010, variables['target_year'] + 1))
    fees = list(range(5, 5 + len(index)))
    df = pd.DataFrame(fees, index=index, columns=['Fees'])
    df['Forecast'] = False
    df.loc[df.index > 2019, 'Forecast'] = True
    return df


if __name__ == '__main__':
    df = predict_parking_fees(skip_cache=True)
    print(df)
