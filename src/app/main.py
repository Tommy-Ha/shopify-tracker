from dash import Dash,dash_table
from dash import Input, State
from dash import Output
from dash import html
from dash import dcc
import dash_ag_grid as dag
import dash_bootstrap_components as dbc

from src import inventory
from src import tracker
from src.config import settings
from src.db import utils
from src import linkHandler

# routes
_ROUTE_ONE_TRACKER_URLS = [
    "https://776bc.com",
    "https://budgysmuggler.com.au",
    "https://www.slixaustralia.com.au/",
    "https://jlathletics.com/",
    "https://nimbleactivewear.com/",
    "https://www.dharmabums.com.au/",
    "https://au.ryderwear.com/",
    "https://www.kozii.com/",
    "https://2xu.com/",
    "https://www.volaresports.com/"
]

_ROUTE_TWO_TRACKER_URLS = [
    "https://www.twinsix.com/",
    "https://hyperfly.com/",
    "https://continuousflowbjj.com/",
    "https://jitsy.club/",
    "https://engageind.com/",
    "https://au.tatamifightwear.com/",
    "https://www.hayabusafight.com/",
    "https://www.albinoandpreto.com/",
    "https://shoyoroll.com/",
    "https://mmafightstore.com.au/"
]


routes = [
    {"id": 1, "href": "/swimming", "tracker_urls": _ROUTE_ONE_TRACKER_URLS},
    {"id": 2, "href": "/boxing", "tracker_urls": _ROUTE_TWO_TRACKER_URLS},
]

home_content = html.Div([
    dbc.Row([
        dbc.Col(
            dcc.Input(id="input-link",type='text',placeholder="https://domain.com")
        ),
        dbc.Col(dcc.Dropdown(id="dropdown-link-type",options=['Swimming','Boxing'],value='Swimming'),),
        dbc.Col([html.Button(id="add-link",children="Add"),html.Button(id="remove-link",children="Remove")]),
    ], style={"padding":"5%"}),
    dash_table.DataTable(
        id='table-links',
        columns=[
            {'name': 'Link', 'id': 'link', 'deletable': True},
        ],
        data=[],
        row_selectable='multi',
        selected_rows=[],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'},
    
    ),
    html.Br(),
    html.H4("Search by type:"),
    dcc.Dropdown(id="dropdown-link-type-search",options=['Swimming','Boxing'],value='Swimming'),

], 
style={"width":"50%","margin":"auto"}
)

# navbar
navbar_contents = [
    dbc.Col(
        dbc.NavbarBrand(
            "Shopify Tracker", class_name="ms-2", href="/"
        )
    ),
    dbc.Col(
        dbc.Nav(
            [
                dbc.NavLink(
                    "Swimming", href="/swimming", active="partial",
                    external_link=False
                ),
                dbc.NavLink(
                    "Boxing", href="/boxing", active="partial",
                    external_link=False
                ),
            ],
            vertical=False,
            pills=False,
        )
    ),
]

navbar = dbc.Navbar(
    dbc.Container(
        [
            dbc.Row(
                navbar_contents,
                align="center",
                class_name="g-0",
            ),
        ]
    ),
    color="dark",
    dark=True,
)


page_content = html.Div(id="page-content")


def _render_select(href: str) -> html.Div:
    tracker_urls, = [
        route["tracker_urls"]
        for route in routes
        if route["href"] == href
    ]

    trackers = tracker.filter_trackers_by_urls(tracker_urls)

    select = dcc.Dropdown(
        options=[
            {"label": tracker.name, "value": tracker.name}
            for tracker in trackers
        ],
        value=trackers[0].name,
        id="selected-tracker",
        searchable=True,
        maxHeight=250,
    )

    contents = html.Div(
        [
            html.Br(),
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("First Updated"),
                                dbc.CardBody(id="first-updated")
                            ]
                        )
                    ),
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader("Last Updated"),
                                dbc.CardBody(id="last-updated")
                            ]
                        )
                    )
                ]
            ),
            html.Br(),
            dag.AgGrid(
                id="inventory-grid",
                dashGridOptions={
                    "pagination": True,
                },
                columnSize="responsiveSizeToFit",
                columnSizeOptions={"skipHeader": False}
            ),
            dbc.Row(
                dbc.Col(select)
            ),
        ]
    )

    return contents


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP],
           prevent_initial_callbacks='initial_duplicate')
app.title = "Shopify Tracker"
app.layout = html.Div(
    children=[
        dcc.Location(id="url"),
        navbar,
        page_content
    ]
)

@app.callback(
        [Output('table-links','data'),
        Output("input-link","value")],
        [Input("add-link","n_clicks"),
         State("dropdown-link-type","value"),
         State("input-link","value")
         ],         
        prevent_initial_cal=True
)
def insert_link(n_clicks,type,link):
    if n_clicks != None:
        print(linkHandler.insert_link(link,type))
    result=linkHandler.select_link_by_type()
    return result,""

@app.callback(
    Output('table-links', 'data',allow_duplicate=True),
    Input('remove-link', 'n_clicks'),
    State('table-links', 'selected_rows') ,
    State('table-links', 'data'),
    prevent_initial_call=True
)
def delete_selected_row(n_clicks,selected_rows,rows):
    if n_clicks>0 and selected_rows:
        try:
            for i in range(0,len(selected_rows)):
                row_id=rows[selected_rows[i]]["link"]
                linkHandler.remove_link(row_id)
                rows.pop(selected_rows[0])
        except Exception as e:
            print(e)
    return rows


@app.callback(
        Output("table-links","data",allow_duplicate=True),
        Input("dropdown-link-type-search","value")
)
def search_by_type(value):
    if value:
        return linkHandler.select_link_by_type(value)
    else:
        return linkHandler.select_link_by_type()

@app.callback(
    Output("page-content", "children"),
    [
        Input("url", "pathname"),
    ]
)
def render_page_content(pathname):
    if pathname == "/swimming":
        return html.Div(
            [
                _render_select(pathname)
            ]
        )

    elif pathname == "/boxing":
        return html.Div([
                _render_select(pathname)
            ])
    
    elif pathname == "/":
        return home_content

    else:
        return html.Div(
            [
                html.H1("404: Not found", className="text-danger"),
                html.Hr(),
                html.P(f"The pathname {pathname} was not recognised..."),
            ],
            className="p-3 bg-light rounded-3",
        )


@app.callback(
    [
        Output("inventory-grid", "columnDefs"),
        Output("inventory-grid", "rowData"),
        Output("first-updated", "children"),
        Output("last-updated", "children"),
    ],
    Input("selected-tracker", "value")
)
def render_table(tracker_name: str):
    engine = utils.get_engine(
        url=f"sqlite:///{settings.SQLITE_DB_ROOT}/{tracker_name}.db"
    )

    df = inventory.compute_inventory(engine)

    table_cols = [
        "product_title",
        "product_type",
        "variant_title",
        "initial_amount",
        "item_sold"
    ]

    columnDefs = [
        {"field": "product_title", "headerName": "Product Title"},
        {"field": "product_type", "headerName": "Product Type"},
        {"field": "variant_title", "headerName": "Variant Title"},
        {"field": "initial_amount", "headerName": "Initial Amount"},
        {"field": "item_sold", "headerName": "Item Sold"},
    ]
    rowData = df[table_cols].to_dict(orient="records")

    first_updated = df["first_updated"].min()
    last_updated = df["last_updated"].max()

    return columnDefs, rowData, first_updated, last_updated


def main() -> int:
    app.run()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
