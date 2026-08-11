from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st


MAP_COMPONENT_HTML = """
<div class="hj-map-shell">
  <div class="hj-map" role="application" aria-label="Interactive hike map"></div>
  <div class="hj-map-loading" aria-live="polite">Loading this area…</div>
  <div class="hj-map-legend" aria-label="Route colors">
    <span><i class="hj-map-line hj-map-line--florida"></i>Florida Trail · USFS / FTA</span>
    <span><i class="hj-map-line hj-map-line--recorded"></i>Your recorded route</span>
    <span><i class="hj-map-line hj-map-line--shared"></i>Shared route</span>
  </div>
</div>
"""

MAP_COMPONENT_CSS = """
@import url('https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css');
:host { display:block; width:100%; height:100%; color:#14231b; font-family:'Manrope',sans-serif; }
.hj-map-shell { position:relative; width:100%; height:100%; min-height:520px; overflow:hidden; border-radius:16px; background:#dfe8e2; }
.hj-map { position:absolute; inset:0; }
.hj-map-loading { position:absolute; left:50%; top:16px; z-index:5; transform:translate(-50%,-10px); opacity:0; pointer-events:none; padding:8px 12px; border-radius:999px; background:rgba(20,35,27,.88); color:#fff; font-size:12px; font-weight:800; transition:opacity .16s ease,transform .16s ease; }
.hj-map-shell.is-loading .hj-map-loading { opacity:1; transform:translate(-50%,0); }
.hj-map-legend { position:absolute; right:10px; bottom:30px; z-index:4; display:grid; gap:5px; color:#fff; font-size:11px; font-weight:800; letter-spacing:.02em; text-shadow:0 1px 3px rgba(0,0,0,.95),0 0 7px rgba(0,0,0,.65); pointer-events:none; }
.hj-map-legend span { display:flex; align-items:center; justify-content:flex-end; gap:7px; }
.hj-map-line { display:inline-block; width:24px; height:4px; box-shadow:0 1px 3px rgba(0,0,0,.8); }
.hj-map-line--florida { background:#f47a32; }
.hj-map-line--recorded { background:#22d3ee; }
.hj-map-line--shared { background:#ff4d8d; }
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
@media (max-width:640px) { .hj-map-shell { min-height:500px; border-radius:12px; } .hj-basemap { top:8px; left:8px; } .hj-map-legend { right:8px; bottom:28px; font-size:10px; } .maplibregl-ctrl-top-right { top:0; right:0; } }
"""

MAP_COMPONENT_JS = r"""
const MAPLIBRE_URL = 'https://esm.sh/maplibre-gl@5.6.1';
const FLORIDA_TRAIL_GEOJSON_URL = 'https://services9.arcgis.com/soy9dtLUh5hYXg8U/arcgis/rest/services/FNST%20Master/FeatureServer/0/query?where=1%3D1&outFields=FID&returnGeometry=true&outSR=4326&f=geojson&maxAllowableOffset=0.00002';
const EMPTY = {type:'FeatureCollection',features:[]};
const OVERLAP_DISTANCE_METERS = 45;
const MINIMUM_DIRECTION_SIMILARITY = .72;
const ROUTE_CHUNK_METERS = 20;
const GRID_CELL_METERS = 120;
const EARTH_RADIUS_METERS = 6378137;

function projected(point) {
  const latitude=Math.max(-85,Math.min(85,point[1]))*Math.PI/180;
  return {x:EARTH_RADIUS_METERS*point[0]*Math.PI/180,y:EARTH_RADIUS_METERS*Math.log(Math.tan(Math.PI/4+latitude/2))};
}
function segment(a,b) {
  const start=projected(a),end=projected(b),dx=end.x-start.x,dy=end.y-start.y;
  return {start,end,dx,dy,length:Math.hypot(dx,dy)};
}
function lineCoordinates(geojson) {
  const lines=[];
  for (const feature of geojson?.features||[]) {
    const geometry=feature?.geometry;
    if (geometry?.type==='LineString') lines.push(geometry.coordinates);
    if (geometry?.type==='MultiLineString') lines.push(...geometry.coordinates);
  }
  return lines.filter(line=>line.length>1);
}
function cell(value) { return Math.floor(value/GRID_CELL_METERS); }
function cellKey(x,y) { return `${x}:${y}`; }
function buildTrailIndex(geojson) {
  const cells=new Map();
  for (const line of lineCoordinates(geojson)) for (let i=1;i<line.length;i++) {
    const item=segment(line[i-1],line[i]);
    if (item.length<.5) continue;
    const minX=cell(Math.min(item.start.x,item.end.x)-OVERLAP_DISTANCE_METERS);
    const maxX=cell(Math.max(item.start.x,item.end.x)+OVERLAP_DISTANCE_METERS);
    const minY=cell(Math.min(item.start.y,item.end.y)-OVERLAP_DISTANCE_METERS);
    const maxY=cell(Math.max(item.start.y,item.end.y)+OVERLAP_DISTANCE_METERS);
    for (let x=minX;x<=maxX;x++) for (let y=minY;y<=maxY;y++) {
      const key=cellKey(x,y),bucket=cells.get(key)||[]; bucket.push(item); cells.set(key,bucket);
    }
  }
  return cells;
}
function directionSimilarity(a,b) {
  return Math.abs(a.dx*b.dx+a.dy*b.dy)/(a.length*b.length);
}
function distanceToSegment(point,item) {
  const squared=item.dx*item.dx+item.dy*item.dy;
  const amount=squared===0?0:Math.max(0,Math.min(1,((point.x-item.start.x)*item.dx+(point.y-item.start.y)*item.dy)/squared));
  return Math.hypot(point.x-(item.start.x+amount*item.dx),point.y-(item.start.y+amount*item.dy));
}
function overlapsTrail(a,b,index) {
  const user=segment(a,b);
  if (user.length<.5) return false;
  const midpoint={x:(user.start.x+user.end.x)/2,y:(user.start.y+user.end.y)/2};
  return (index.get(cellKey(cell(midpoint.x),cell(midpoint.y)))||[]).some(trail=>
    directionSimilarity(user,trail)>=MINIMUM_DIRECTION_SIMILARITY && distanceToSegment(midpoint,trail)<=OVERLAP_DISTANCE_METERS
  );
}
function interpolate(a,b,amount) { return [a[0]+(b[0]-a[0])*amount,a[1]+(b[1]-a[1])*amount]; }
function overlappingRouteFeatures(routes,index) {
  const features=[];
  for (const line of lineCoordinates(routes)) for (let i=1;i<line.length;i++) {
    const edge=segment(line[i-1],line[i]);
    const chunks=Math.max(1,Math.min(5000,Math.ceil(edge.length/ROUTE_CHUNK_METERS)));
    let active=[];
    for (let chunk=0;chunk<chunks;chunk++) {
      const from=interpolate(line[i-1],line[i],chunk/chunks),to=interpolate(line[i-1],line[i],(chunk+1)/chunks);
      if (overlapsTrail(from,to,index)) { if (!active.length) active.push(from); active.push(to); }
      else if (active.length) { features.push({type:'Feature',properties:{},geometry:{type:'LineString',coordinates:active}}); active=[]; }
    }
    if (active.length) features.push({type:'Feature',properties:{},geometry:{type:'LineString',coordinates:active}});
  }
  return {type:'FeatureCollection',features};
}

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
  map.addSource('florida-trail',{type:'geojson',data:FLORIDA_TRAIL_GEOJSON_URL});
  map.addLayer({id:'florida-trail-halo',type:'line',source:'florida-trail',paint:{'line-color':'#4d2b17','line-width':['interpolate',['linear'],['zoom'],7,2.5,15,6],'line-opacity':.58}});
  map.addLayer({id:'florida-trail',type:'line',source:'florida-trail',paint:{'line-color':'#f47a32','line-width':['interpolate',['linear'],['zoom'],7,1.5,15,3.5],'line-opacity':.96}});
  map.addSource('routes',{type:'geojson',data:EMPTY});
  map.addLayer({id:'route-halo',type:'line',source:'routes',paint:{'line-color':'#263228','line-width':['interpolate',['linear'],['zoom'],7,3.5,15,8],'line-opacity':.72}});
  map.addLayer({id:'routes',type:'line',source:'routes',paint:{'line-color':'#22d3ee','line-width':['interpolate',['linear'],['zoom'],7,1.8,15,4.5],'line-opacity':.98}});
  map.addSource('route-overlap',{type:'geojson',data:EMPTY});
  map.addLayer({id:'route-overlap',type:'line',source:'route-overlap',paint:{'line-color':'#ff4d8d','line-width':['interpolate',['linear'],['zoom'],7,2.2,15,5.2],'line-opacity':1}});
  map.addSource('markers',{type:'geojson',data:EMPTY});
  const clusterFilter = ['==',['get','kind'],'cluster'];
  const pointFilter = ['==',['get','kind'],'point'];
  map.addLayer({id:'clusters',type:'circle',source:'markers',filter:clusterFilter,paint:{
    'circle-radius':['interpolate',['linear'],['get','count'],2,15,100,24,1000,32],
    'circle-color':['match',['get','layer'],'species','#30473a','#73a9ba'],
    'circle-stroke-color':'#f6f0e4','circle-stroke-width':2,'circle-opacity':.94
  }});
  map.addLayer({id:'cluster-count',type:'symbol',source:'markers',filter:clusterFilter,layout:{'text-field':['to-string',['get','count']],'text-size':12,'text-font':['Open Sans Bold']},paint:{'text-color':'#fff'}});
  map.addLayer({id:'photo-points',type:'circle',source:'markers',filter:['all',pointFilter,['==',['get','layer'],'photo']],paint:{'circle-radius':6,'circle-color':'#8bd3ff','circle-stroke-color':'#123b4a','circle-stroke-width':2}});
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
    state={map,maplibregl,loaded:false,popup:null,detailId:null,moveTimer:null,trailIndex:null,routes:data.routes||EMPTY}; shell.__hjMapState=state;
    map.on('load',()=>{
      addDataLayers(map); state.loaded=true;
      map.getSource('markers').setData(data.markers||EMPTY); map.getSource('routes').setData(data.routes||EMPTY);
      fetch(FLORIDA_TRAIL_GEOJSON_URL).then(response=>response.ok?response.json():null).then(trail=>{
        if (!trail) return; state.trailIndex=buildTrailIndex(trail);
        map.getSource('route-overlap')?.setData(overlappingRouteFeatures(state.routes,state.trailIndex));
      }).catch(()=>{});
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
    state.routes=data.routes||EMPTY;
    state.map.getSource('route-overlap')?.setData(state.trailIndex?overlappingRouteFeatures(state.routes,state.trailIndex):EMPTY);
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
