from calc import calcfunc


@calcfunc(
    datasets=dict(
        emissions='jyrjola/lipasto/emissions_by_municipality',
    ),
    variables=[
        'municipality_name'
    ]
)
def prepare_transportation_emissions_dataset(datasets, variables):
    df = datasets['emissions']
    df = df[df.Municipality == variables['municipality_name']].copy()
    df = df.drop(columns='index')
    df = df.drop(columns='Municipality')
    df.Vehicle = df.Vehicle.astype('category')
    df.Road = df.Road.astype('category')
    return df
