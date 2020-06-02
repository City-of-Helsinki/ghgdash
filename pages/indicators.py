import yaml
import dash_cytoscape as cyto

from .base import Page
import dash_bootstrap_components as dbc
import dash_html_components as html
from dash.dependencies import Input, Output


cyto.load_extra_layouts()


FONT_FAMILY = 'Arial'

STYLES = [
    {
        'selector': '*',
        'style': {
            # 'font-family': FONT_FAMILY,
        },
    }, {
        'selector': 'node',
        'style': {
            'label': 'data(label)',
            #'text-wrap': 'wrap',
            #'text-outline-width': 0,
            'color': '#ffffff',
            #'font-weight': '500',
            'shape': 'rectangle',
            'width': 'label',
            'height': 'label',
            'text-valign': 'center',
            'padding': '24px',
        },
    }, {
        'selector': 'edge',
        'style': {
            'label': 'data(label)',
            'target-text-offset': 1,
            'target-arrow-shape': 'triangle',
            'target-arrow-color': 'data(color)',
            'arrow-scale': 2,
            'line-color': 'data(color)',
            'text-outline-width': 3,
            'text-outline-color': 'data(color)',
            'color': '#ffffff',
            'curve-style': 'bezier',
            'font-size': '18px',
            'font-weight': '600',
            'width': 2,
        },
    }, {
        'selector': 'node[type="emissions"]',
        'style': {
            'background-color': 'rgb(0, 110, 178)',
            'color': '#ffffff',
            'shape': 'rectangle',
            'width': 'label',
            'height': 'label',
        },
    }, {
        'selector': 'node[type="emission_factor"]',
        'style': {
            'background-color': 'rgb(0, 215, 167)',
            'color': '#000000',
            'shape': 'rectangle',
            'width': 'label',
            'height': 'label',
        },
    }, {
        'selector': 'node[type="activity"]',
        'style': {
            'background-color': 'rgb(253, 79, 0)',
            'color': '#000000',
        },
    },
]


class IndicatorPage(Page):
    id = 'indicators'
    path = '/indicators'
    name = 'Indicators'

    def cytoscape_event_callback(self, tapdata):
        return [None]

    def __init__(self):
        super().__init__()
        wrapper = self.callback(
            inputs=[Input('indicator-graph', 'tapNodeData')],
            outputs=[Output('indicator-output', 'children')]
        )
        wrapper(self.cytoscape_event_callback)

    def make_elements(self):
        inds = yaml.load(open('indicators.yaml', 'r'), Loader=yaml.SafeLoader)['indicators']
        nodes = []
        edges = []
        for ind in inds:
            node = dict(data={
                'label': ind['name_fi']
            })
            node['data'].update(ind)
            nodes.append(node)

            if 'output' in ind:
                edges.append(dict(data={
                    'source': ind['id'],
                    'target': ind['output'],
                    'color': 'green' if ind['output_effect'] == '+' else 'red',
                }))

        return nodes + edges

    def render(self):
        dag = cyto.Cytoscape(
            id='indicator-graph',
            layout={
                'name': 'dagre',
                'ranker': 'longest-path',
                'nodeDimensionsIncludeLabels': True,
                'avoidOverlap': True,
                'fit': True,
                'nodeSep': 300,
            },
            # stylesheet=default_stylesheet,
            style={'width': '100%', 'height': '1000px'},
            elements=self.make_elements(),
            stylesheet=STYLES,
            zoomingEnabled=True,
            maxZoom=2,
            minZoom=0.1,
        )
        self.make_elements()

        ret = html.Div([
            self._make_navbar(),
            dbc.Container(
                [
                    dbc.Row([dag]),
                    dbc.Row(html.Div(id='indicator-output'))
                ],
                className="app-content",
                fluid=True
            )
        ])
        return ret
