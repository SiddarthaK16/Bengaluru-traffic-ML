import * as maplibregl from 'https://unpkg.com/maplibre-gl@6.12.0/dist/maplibre-gl.mjs';

const map = new maplibregl.Map({
  container: 'map',
  style: 'https://tiles.openfreemap.org/styles/liberty',
  center: [77.5946, 12.9716],
  zoom: 11,
  attributionControl: true,
});
map.addControl(new maplibregl.NavigationControl(), 'bottom-right');

const palette = { free: '#71d8aa', busy: '#f4bc59', slow: '#f07866' };
let chosenPoint = 'origin';
let origin = null;
let destination = null;
let trafficMarkers = [];
let choiceMarkers = [];
let routeAdded = false;

const originButton = document.getElementById('origin-button');
const destinationButton = document.getElementById('destination-button');
const routeButton = document.getElementById('route-button');
const errorMessage = document.getElementById('error-message');

function trafficLevel(ratio) {
  if (ratio === null || ratio === undefined) return 'busy';
  if (ratio < 0.5) return 'slow';
  if (ratio < 0.8) return 'busy';
  return 'free';
}

function formattedTime(value) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function setActiveChoice(choice) {
  chosenPoint = choice;
  originButton.classList.toggle('selected', choice === 'origin');
  destinationButton.classList.toggle('selected', choice === 'destination');
  document.getElementById('map-hint').textContent = `Click the map to set ${choice}`;
}

function updatePointLabels() {
  document.getElementById('origin-label').textContent = origin ? `${origin.lat.toFixed(5)}, ${origin.lon.toFixed(5)}` : 'Choose on map';
  document.getElementById('destination-label').textContent = destination ? `${destination.lat.toFixed(5)}, ${destination.lon.toFixed(5)}` : 'Choose on map';
  routeButton.disabled = !origin || !destination;
  for (const marker of choiceMarkers) marker.remove();
  choiceMarkers = [];
  for (const [point, name] of [[origin, 'origin'], [destination, 'destination']]) {
    if (!point) continue;
    const element = document.createElement('span');
    element.className = `route-marker ${name}`;
    choiceMarkers.push(new maplibregl.Marker({ element, anchor: 'center' })
      .setLngLat([point.lon, point.lat])
      .setPopup(new maplibregl.Popup({ offset: 12 }).setText(name === 'origin' ? 'Origin' : 'Destination'))
      .addTo(map));
  }
  document.getElementById('map-hint').textContent = origin && destination
    ? 'Route points selected · choose a departure time'
    : `Click the map to set ${origin ? 'destination' : 'origin'}`;
}

map.on('click', (event) => {
  const point = { lat: event.lngLat.lat, lon: event.lngLat.lng };
  if (chosenPoint === 'origin') {
    origin = point;
    setActiveChoice('destination');
  } else {
    destination = point;
    setActiveChoice('origin');
  }
  updatePointLabels();
});

originButton.addEventListener('click', () => setActiveChoice('origin'));
destinationButton.addEventListener('click', () => setActiveChoice('destination'));

function renderTraffic(records, updatedAt) {
  for (const marker of trafficMarkers) marker.remove();
  trafficMarkers = [];
  for (const record of records) {
    if (record.latitude == null || record.longitude == null) continue;
    const level = trafficLevel(record.congestion_ratio);
    const element = document.createElement('span');
    element.className = `traffic-marker ${level}`;
    const speed = record.current_speed_kmh == null ? '—' : `${record.current_speed_kmh} km/h`;
    const ratio = record.congestion_ratio == null ? 'unavailable' : `${Math.round(record.congestion_ratio * 100)}% of free-flow speed`;
    const forecast = record.predicted_congestion_ratio == null
      ? '15 min forecast unavailable'
      : `15 min forecast: ${Math.round(record.predicted_congestion_ratio * 100)}% of free-flow speed`;
    const popup = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'popup-title';
    title.textContent = record.location.replaceAll('_', ' ');
    const details = document.createElement('div');
    details.className = 'popup-sub';
    details.append(`${speed} · ${ratio}`, document.createElement('br'), forecast, document.createElement('br'), `Observed ${formattedTime(record.timestamp)}`);
    popup.append(title, details);
    trafficMarkers.push(new maplibregl.Marker({ element, anchor: 'center' })
      .setLngLat([record.longitude, record.latitude])
      .setPopup(new maplibregl.Popup({ offset: 12 }).setDOMContent(popup))
      .addTo(map));
  }
  document.getElementById('location-count').textContent = `${records.length} / ${document.getElementById('location-count').dataset.expected || records.length}`;
  document.getElementById('live-label').textContent = updatedAt ? `Feed updated ${formattedTime(updatedAt)}` : 'No traffic observations yet';
}

async function refreshTraffic() {
  try {
    const response = await fetch('/api/traffic/latest');
    if (!response.ok) throw new Error(response.status === 503 ? 'Traffic database is unavailable' : 'Could not load traffic readings');
    const data = await response.json();
    const count = document.getElementById('location-count');
    count.dataset.expected = data.expected_locations;
    renderTraffic(data.records, data.updated_at);
  } catch (error) {
    document.getElementById('live-label').textContent = 'Traffic feed unavailable';
    errorMessage.textContent = error.message;
    errorMessage.classList.remove('hidden');
  }
}

function duration(seconds) {
  const minutes = Math.round(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return hours ? `${hours}h ${remainder}m` : `${minutes} min`;
}

function clearRouteResult() {
  if (routeAdded && map.getLayer('route-line')) map.removeLayer('route-line');
  if (routeAdded && map.getSource('route')) map.removeSource('route');
  routeAdded = false;
  document.getElementById('route-result').classList.add('hidden');
  errorMessage.classList.add('hidden');
}

async function calculateRoute() {
  if (!origin || !destination) return;
  routeButton.disabled = true;
  routeButton.firstElementChild.textContent = 'Finding the fastest route…';
  errorMessage.classList.add('hidden');
  try {
    const params = new URLSearchParams({
      origin_lat: origin.lat,
      origin_lon: origin.lon,
      destination_lat: destination.lat,
      destination_lon: destination.lon,
    });
    const departure = document.getElementById('departure-time').value;
    if (departure) params.set('departure_time', new Date(departure).toISOString());
    const response = await fetch(`/api/route?${params}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not calculate this route');

    clearRouteResult();
    map.addSource('route', { type: 'geojson', data: { type: 'Feature', properties: {}, geometry: data.geometry } });
    map.addLayer({
      id: 'route-line', type: 'line', source: 'route',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': '#176b51', 'line-width': 6, 'line-opacity': 0.93 },
    });
    routeAdded = true;
    document.getElementById('route-duration').textContent = duration(data.travel_time_seconds);
    document.getElementById('route-distance').textContent = `${(data.length_meters / 1000).toFixed(1)} km`;
    document.getElementById('route-delay').textContent = data.traffic_delay_seconds > 0 ? `+${duration(data.traffic_delay_seconds)} traffic` : 'Low traffic delay';
    document.getElementById('arrival-time').textContent = formattedTime(data.arrival_time);
    document.getElementById('route-result').classList.remove('hidden');
    const bounds = new maplibregl.LngLatBounds();
    for (const coordinate of data.geometry.coordinates) bounds.extend(coordinate);
    map.fitBounds(bounds, { padding: 60, maxZoom: 14 });
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.classList.remove('hidden');
  } finally {
    routeButton.disabled = !origin || !destination;
    routeButton.firstElementChild.textContent = 'Calculate my trip';
  }
}

routeButton.addEventListener('click', calculateRoute);
document.getElementById('clear-button').addEventListener('click', () => {
  origin = null;
  destination = null;
  setActiveChoice('origin');
  updatePointLabels();
  clearRouteResult();
});

const departureInput = document.getElementById('departure-time');
const initialDeparture = new Date(Date.now() + 15 * 60 * 1000);
initialDeparture.setMinutes(Math.ceil(initialDeparture.getMinutes() / 5) * 5, 0, 0);
departureInput.value = new Date(initialDeparture.getTime() - initialDeparture.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

setActiveChoice('origin');
updatePointLabels();
refreshTraffic();
window.setInterval(refreshTraffic, 60_000);
