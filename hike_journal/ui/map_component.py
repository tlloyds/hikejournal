from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


MAP_COMPONENT_HTML = """
<div class="hj-map-shell">
  <div class="hj-map" role="application" aria-label="Interactive hike map"></div>
  <div class="hj-map-loading" aria-live="polite">Loading this area…</div>
</div>
"""

MAP_COMPONENT_CSS = """
@import url('https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css');
:host { display:block; width:100%; height:100%; color:#14231b; font-family:'Manrope',sans-serif; }
.hj-map-shell { position:relative; width:100%; height:100%; min-height:520px; overflow:hidden; border-radius:16px; background:#dfe8e2; }
.hj-map { position:absolute; inset:0; }
.hj-map-loading { position:absolute; left:50%; top:16px; z-index:5; transform:translate(-50%,-10px); opacity:0; pointer-events:none; padding:8px 12px; border-radius:999px; background:rgba(20,35,27,.88); color:#fff; font-size:12px; font-weight:800; transition:opacity .16s ease,transform .16s ease; }
.hj-map-shell.is-loading .hj-map-loading { opacity:1; transform:translate(-50%,0); }
.maplibregl-ctrl-group { border-radius:10px!important; overflow:hidden; box-shadow:0 5px 18px rgba(20,35,27,.18)!important; }
.maplibregl-popup-content { width:min(310px,calc(100vw - 64px)); padding:0; overflow:hidden; border-radius:14px; box-shadow:0 16px 42px rgba(20,35,27,.24); }
.maplibregl-popup-close-button { z-index:2; width:32px; height:32px; margin:7px; border-radius:50%; background:rgba(20,35,27,.78); color:white; font-size:20px; }
.hj-popup-image { display:block; width:100%; height:180px; object-fit:cover; background:#dfe8e2; }
.hj-popup-body { padding:14px 16px 16px; }
.hj-popup-title { margin:0 0 5px; font-size:15px; font-weight:800; color:#1f2a26; }
.hj-popup-meta { margin:0 0 11px; font-size:12px; line-height:1.5; color:#59665f; }
.hj-popup-species { margin:0 0 12px; padding:0; list-style:none; font-size:12px; line-height:1.55; }
.hj-popup-actions { display:flex; gap:14px; flex-wrap:wrap; }
.hj-popup-actions a { color:#30473a; font-weight:800; text-decoration:none; }
.hj-basemap { position:absolute; top:10px; left:10px; z-index:4; min-height:38px; max-width:138px; border:0; border-radius:10px; padding:0 32px 0 12px; background:rgba(255,255,255,.94); color:#1f2a26; font:700 12px 'Manrope',sans-serif; box-shadow:0 5px 18px rgba(20,35,27,.18); }
@media (max-width:640px) { .hj-map-shell { min-height:500px; border-radius:12px; } .hj-basemap { top:8px; left:8px; } .maplibregl-ctrl-top-right { top:0; right:0; } }
"""

MAP_COMPONENT_JS = r"""
const MAPLIBRE_URL = 'https://esm.sh/maplibre-gl@5.6.1';
const EMPTY = {type:'FeatureCollection',features:[]};

function rasterStyle() {
  return {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {
      satellite: {type:'raster',tiles:['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],tileSize:256,attribution:'Tiles &copy; Esri'},
      topo: {type:'raster',tiles:['https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}'],tileSize:256,attribution:'Tiles &copy; Esri'},
      light: {type:'raster',tiles:['https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png','https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'],tileSize:256,attribution:'&copy; OpenStreetMap &copy; CARTO'},
      street: {type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'&copy; OpenStreetMap contributors'}
    },
    layers: [
      {id:'basemap-satellite',type:'raster',source:'satellite',layout:{visibility:'visible'}},
      {id:'basemap-topo',type:'raster',source:'topo',layout:{visibility:'none'}},
      {id:'basemap-light',type:'raster',source:'light',layout:{visibility:'none'}},
      {id:'basemap-street',type:'raster',source:'street',layout:{visibility:'none'}}
    ]
  };
}

function addDataLayers(map) {
  map.addSource('routes',{type:'geojson',data:EMPTY});
  map.addLayer({id:'route-halo',type:'line',source:'routes',paint:{'line-color':'#f6f0e4','line-width':['interpolate',['linear'],['zoom'],7,3,15,8],'line-opacity':.68}});
  map.addLayer({id:'routes',type:'line',source:'routes',paint:{'line-color':'#30473a','line-width':['interpolate',['linear'],['zoom'],7,1.5,15,4.5],'line-opacity':.96}});
  map.addSource('markers',{type:'geojson',data:EMPTY});
  const clusterFilter = ['==',['get','kind'],'cluster'];
  const pointFilter = ['==',['get','kind'],'point'];
  map.addLayer({id:'clusters',type:'circle',source:'markers',filter:clusterFilter,paint:{
    'circle-radius':['interpolate',['linear'],['get','count'],2,15,100,24,1000,32],
    'circle-color':['match',['get','layer'],'species','#30473a','#73a9ba'],
    'circle-stroke-color':'#f6f0e4','circle-stroke-width':2,'circle-opacity':.94
  }});
  map.addLayer({id:'cluster-count',type:'symbol',source:'markers',filter:clusterFilter,layout:{'text-field':['to-string',['get','count']],'text-size':12,'text-font':['Open Sans Bold']},paint:{'text-color':'#fff'}});
  map.addLayer({id:'photo-points',type:'circle',source:'markers',filter:['all',pointFilter,['==',['get','layer'],'photo']],paint:{'circle-radius':6,'circle-color':'#89b8c7','circle-stroke-color':'#f6f0e4','circle-stroke-width':2}});
  map.addLayer({id:'species-points',type:'circle',source:'markers',filter:['all',pointFilter,['==',['get','layer'],'species']],paint:{'circle-radius':8,'circle-color':'#30473a','circle-stroke-color':'#f6f0e4','circle-stroke-width':2}});
}

function esc(value) {
  const node=document.createElement('span'); node.textContent=value ?? ''; return node.innerHTML;
}
function escAttr(value) {
  return esc(value).replaceAll('"','&quot;').replaceAll("'",'&#39;');
}

function detailHTML(detail) {
  const observations=(detail.observations||[]).map(o=>`<li><strong>${esc(o.common_name||o.scientific_name||'Confirmed species')}</strong>${o.scientific_name?` · <em>${esc(o.scientific_name)}</em>`:''}${o.confidence_label?` · ${esc(o.confidence_label)}`:''}</li>`).join('');
  const title=detail.caption||(detail.observations?.[0]?.common_name)||'Trail photo';
  const date=detail.taken_at?new Date(detail.taken_at).toLocaleString():'';
  return `${detail.image_url?`<img class="hj-popup-image" src="${escAttr(detail.image_url)}" alt="${escAttr(title)}">`:''}<div class="hj-popup-body"><div class="hj-popup-title">${esc(title)}</div><p class="hj-popup-meta">${esc(date)}${date?' · ':''}${Number(detail.lat).toFixed(5)}, ${Number(detail.lng).toFixed(5)}</p>${observations?`<ul class="hj-popup-species">${observations}</ul>`:''}<div class="hj-popup-actions"><a href="${escAttr(detail.viewer_url)}" target="_self">Open viewer</a>${detail.image_url?`<a href="${escAttr(detail.image_url)}" target="_blank" rel="noopener">Full image</a>`:''}</div></div>`;
}

export default async function(component) {
  const {data,setStateValue,parentElement}=component;
  const shell=parentElement.querySelector('.hj-map-shell');
  let state=shell.__hjMapState;
  if (!state) {
    const maplibregl=await import(MAPLIBRE_URL);
    const map=new maplibregl.Map({container:parentElement.querySelector('.hj-map'),style:rasterStyle(),center:data.initial_center||[-81.5,28.4],zoom:data.initial_zoom||8,attributionControl:true});
    map.addControl(new maplibregl.NavigationControl({showCompass:true}),'top-right');
    map.addControl(new maplibregl.FullscreenControl({container:shell}),'top-right');
    map.addControl(new maplibregl.ScaleControl({unit:'imperial'}),'bottom-left');
    const select=document.createElement('select'); select.className='hj-basemap'; select.setAttribute('aria-label','Basemap');
    for (const [value,label] of Object.entries({satellite:'Satellite',topo:'Topo',light:'Light',street:'Street'})) { const option=document.createElement('option'); option.value=value; option.textContent=label; select.appendChild(option); }
    shell.appendChild(select);
    select.onchange=()=>['satellite','topo','light','street'].forEach(name=>map.setLayoutProperty(`basemap-${name}`,'visibility',name===select.value?'visible':'none'));
    state={map,maplibregl,loaded:false,popup:null,detailId:null,moveTimer:null}; shell.__hjMapState=state;
    map.on('load',()=>{
      addDataLayers(map); state.loaded=true;
      map.getSource('markers').setData(data.markers||EMPTY); map.getSource('routes').setData(data.routes||EMPTY);
      if (data.fit_bounds) { state.fitRequest=data.fit_request; map.fitBounds([[data.fit_bounds[0],data.fit_bounds[1]],[data.fit_bounds[2],data.fit_bounds[3]]],{padding:36,maxZoom:15,duration:0}); }
      map.on('click','clusters',e=>{const f=e.features?.[0];if(f)map.easeTo({center:f.geometry.coordinates,zoom:Math.min(map.getZoom()+2.25,18),duration:420});});
      for (const layer of ['photo-points','species-points']) map.on('click',layer,e=>{const f=e.features?.[0];if(!f)return; shell.classList.add('is-loading'); setStateValue('selection',{photo_id:f.properties.photo_id,nonce:Date.now()});});
      for (const layer of ['clusters','photo-points','species-points']) { map.on('mouseenter',layer,()=>map.getCanvas().style.cursor='pointer'); map.on('mouseleave',layer,()=>map.getCanvas().style.cursor=''); }
      map.on('moveend',()=>{clearTimeout(state.moveTimer);state.moveTimer=setTimeout(()=>{const b=map.getBounds();shell.classList.add('is-loading');setStateValue('viewport',{west:b.getWest(),south:b.getSouth(),east:b.getEast(),north:b.getNorth(),zoom:map.getZoom()});},180);});
    });
  }
  if (state.loaded) {
    state.map.getSource('markers')?.setData(data.markers||EMPTY);
    state.map.getSource('routes')?.setData(data.routes||EMPTY);
    shell.classList.remove('is-loading');
    if (data.fit_bounds && data.fit_request !== state.fitRequest) {
      state.fitRequest=data.fit_request;
      state.map.fitBounds([[data.fit_bounds[0],data.fit_bounds[1]],[data.fit_bounds[2],data.fit_bounds[3]]],{padding:36,maxZoom:15,duration:360});
    }
  }
  if (data.detail && data.detail.photo_id!==state.detailId) {
    state.detailId=data.detail.photo_id;
    state.popup?.remove();
    state.popup=new state.maplibregl.Popup({closeButton:true,maxWidth:'330px'}).setLngLat([data.detail.lng,data.detail.lat]).setHTML(detailHTML(data.detail)).addTo(state.map);
    state.map.easeTo({center:[data.detail.lng,data.detail.lat],zoom:Math.max(state.map.getZoom(),15),duration:380});
  }
}
"""


maplibre_component = st.components.v2.component(
    "hikejournal_maplibre",
    html=MAP_COMPONENT_HTML,
    css=MAP_COMPONENT_CSS,
    js=MAP_COMPONENT_JS,
)


def render_maplibre(
    *,
    key: str,
    markers: dict[str, Any],
    routes: dict[str, Any],
    fit_bounds: tuple[float, float, float, float] | None,
    fit_request: str | None,
    detail: dict[str, Any] | None,
) -> Any:
    center = None
    if fit_bounds:
        center = [(fit_bounds[0] + fit_bounds[2]) / 2, (fit_bounds[1] + fit_bounds[3]) / 2]
    return maplibre_component(
        data={
            "markers": markers,
            "routes": routes,
            "fit_bounds": list(fit_bounds) if fit_bounds else None,
            "fit_request": fit_request,
            "initial_center": center,
            "initial_zoom": 8,
            "detail": detail,
        },
        default={"viewport": None, "selection": None},
        key=key,
        height=620,
        width="stretch",
        on_viewport_change=lambda: None,
        on_selection_change=lambda: None,
    )


def map_viewer_url(detail: dict[str, Any], *, selected_hike_id: str | None) -> str:
    photo_id = escape(str(detail.get("photo_id") or ""), quote=True)
    if selected_hike_id:
        hike_id = escape(str(selected_hike_id), quote=True)
        return f"?hike={hike_id}&view=Map&photo={photo_id}"
    return f"?view=Map&scope=global&photo={photo_id}"
