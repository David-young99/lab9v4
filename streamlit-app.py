import math
import pandas as pd
import geopandas as gpd
import plotly.express as px
import folium
from folium import Marker
from folium.plugins import MarkerCluster
from folium.plugins import HeatMap
from streamlit_folium import folium_static


import streamlit as st
#
# Configuración de la página
#
st.set_page_config(layout='wide')

#
# TÍTULO Y DESCRIPCIÓN DE LA APLICACIÓN
#

st.title('Visualización de datos de biodiversidad, fuente: Infraestructura Mundial de Información en Biodiversidad (GBIF)')
st.markdown('Esta aplicación presenta visualizaciones tabulares, gráficas y geoespaciales de datos de biodiversidad que siguen el estándar [Darwin Core (DwC)](https://dwc.tdwg.org/terms/).')
st.markdown('El usuario debe de seleccionar y subir un archivo csv con el formato de [Infraestructura Mundial de Información en Biodiversidad (GBIF)](https://www.gbif.org/).')

#
# ENTRADAS ##############################################################################################################
#

# Carga de los datos.
archivo = st.sidebar.file_uploader('Seleccione un archivo CSV que siga el estándar DwC')

# Procesamiento de los datos cargados previamente
if archivo is not None:
    # Carga de registros de presencia en un dataframe
    observaciones = pd.read_csv(archivo, delimiter='\t')
    # de dataframe a geodataframe
    observaciones = gpd.GeoDataFrame(observaciones, 
                                           geometry=gpd.points_from_xy(observaciones.decimalLongitude, 
                                                                       observaciones.decimalLatitude),
                                           crs='EPSG:4326')

    # carga del geojson
    cr_cantones = gpd.read_file("Data/cr_cantones.geojson")

    # Limpieza de datos
    # Eliminación de registros con valores nulos en la columna 'species'
    observaciones = observaciones[observaciones['species'].notna()]
    # Cambio del tipo de datos del campo de fecha
    observaciones["eventDate"] = pd.to_datetime(observaciones["eventDate"])

    # Especificación de filtros
    # Especie
    lista_especies = observaciones.species.unique().tolist()
    lista_especies.sort()
    filtro_especie = st.sidebar.selectbox('Seleccione la especie', lista_especies)

    #
    # PROCESAMIENTO #######################################################################################################
    #

    # Filtrado
    observaciones = observaciones[observaciones['species'] == filtro_especie]

    # Cálculo de la cantidad de registros
    # "Join" espacial de las capas de cantones y registros de presencia de especies
    cantones_observaciones = cr_cantones.sjoin(observaciones, how="left", predicate="contains")
    # Conteo de registros de presencia en cada provincia
    canton_obs = cantones_observaciones.groupby("CODNUM").agg(cantidad_registros_presencia = ("gbifID","count"))
    canton_obs = canton_obs.reset_index()

    #
    # SALIDAS ##############################################################################################################
    #

    # Creación de la tabla en la web
    st.header('Tabla con las especies observadas/registradas')
    st.dataframe(observaciones[['eventDate','stateProvince', 'locality', 'species','occurrenceID']].rename(columns = {'species':'Especie', 'stateProvince':'Provincia', 'locality':'Localidad', 'eventDate':'Fecha y hora de observación', 'occurrenceID': "Fuente del dato"}))

    # join para Gráfico de observaciones por provincia
    # "Join" para agregar la columna con el conteo a la capa de cantón, nos sirve para conectar pero para el gráfico usará otro atributo de provincia
    canton_obs = canton_obs.join(cr_cantones.set_index('CODNUM'), on='CODNUM', rsuffix='_b')
    # Dataframe filtrado para usar en graficación
    canton_obs_para_grafico = canton_obs.loc[canton_obs['cantidad_registros_presencia'] > 0, 
                                                            ["provincia", "cantidad_registros_presencia"]].sort_values("cantidad_registros_presencia", ascending=True)
    canton_obs_para_grafico = canton_obs_para_grafico.set_index('provincia')  


    # Gráfico de observaciones por provincia
    st.header('Especies observadas/registradas por provincia')

    fig = px.bar(canton_obs_para_grafico, 
                    labels={'provincia':'Provincias de Costa Rica', 'cantidad_registros_presencia':'Registros de presencia'})    

    fig.update_layout(barmode='stack', xaxis={'categoryorder': 'total descending'})
    st.plotly_chart(fig)    
 
    
    # join para Gráfico de observaciones por cantón
    # "Join" para agregar la columna con el conteo a la capa de cantón
    canton_obs = canton_obs.join(cr_cantones.set_index('CODNUM'), on='CODNUM', rsuffix='_b')
    # Dataframe filtrado para usar en graficación
    canton_obs_para_grafico = canton_obs.loc[canton_obs['cantidad_registros_presencia'] > 0, 
                                                            ["NCANTON", "cantidad_registros_presencia"]].sort_values("cantidad_registros_presencia")
    canton_obs_para_grafico = canton_obs_para_grafico.set_index('NCANTON')  


    # Gráfico de observaciones por cantoón
    st.header('Especies observadas/registradas por cantón')

    fig = px.bar(canton_obs_para_grafico, 
                    labels={'NCANTON':'Cantones de Costa Rica', 'cantidad_registros_presencia': 'Registros de presencia'})    

    fig.update_layout(barmode='stack', xaxis={'categoryorder': 'total descending'})
    st.plotly_chart(fig)

    #### Cartografías ############

    # Mapas de coropletas
    st.header('Mapa con las especies observadas/registradas')
    # Capa base
    m = folium.Map(
    location=[10, -84],
    zoom_start=7,
    control_scale=True)

    # Se añaden capas base adicionales para el basemap
    folium.TileLayer(
    tiles='http://services.arcgisonline.com/arcgis/rest/services/NatGeo_World_Map/MapServer/MapServer/tile/{z}/{y}/{x}',
    name='NatGeo World Map',
    attr='ESRI NatGeo World Map').add_to(m)

        # Mapa de coropletas
    folium.Choropleth(
        name="Coropletas de las observaciones por cantón",
        geo_data=cr_cantones,
        data=canton_obs,
        columns=['CODNUM', 'cantidad_registros_presencia'],
        bins=8,
        key_on='feature.properties.CODNUM',
        fill_color='BuPu', 
        fill_opacity=0.5, 
        line_opacity=1,
        legend_name='Registro cantón',
        smooth_factor=0).add_to(m)
    folium.Choropleth(
        name="Coropletas de las observaciones por provincia",
        geo_data=cr_cantones,
        data=canton_obs,
        columns=['provincia', 'cantidad_registros_presencia'],
        bins=8,
        key_on='feature.properties.provincia',
        fill_color='BuGn', 
        fill_opacity=0.5, 
        line_opacity=1,
        legend_name='Registros provincia',
        smooth_factor=0).add_to(m)

    # Capa de las observaciones de especies agrupados en puntos
    mc = MarkerCluster(name='Registros agrupados en marcas en observaciones/registros')
    for idx, row in observaciones.iterrows():
        if not math.isnan(row['decimalLongitude']) and not math.isnan(row['decimalLatitude']):
            mc.add_child(
                Marker([row['decimalLatitude'], row['decimalLongitude'], ], 
                                popup= str(row["species"]) + " - - " + str(row["stateProvince"]) + " - - " + str(row["eventDate"])))
    m.add_child(mc)
    # Control de capas
    folium.LayerControl().add_to(m) 
    # Despliegue del mapa
    folium_static(m)
