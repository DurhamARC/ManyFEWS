import './sass/main.scss';

var floodOverlayLayerGroup = L.layerGroup();

function getFloodOverlays(map) {
  var day = 1
  var bounding_box = map.getBounds();
  var dataUrl = '/depths/1/' + bounding_box.getSouth() + ',' + bounding_box.getWest() + ','
    + bounding_box.getNorth() + ',' + bounding_box.getEast();
  fetch(dataUrl)
    .then(function(resp) {
      return resp.json();
    })
    .then(function(data) {
      floodOverlayLayerGroup.clearLayers();
      console.log(data);
      data["items"].forEach(i => {
        floodOverlayLayerGroup.addLayer(
          L.rectangle(i.bounds,
            {
              color: null,
              fillColor: 'CornflowerBlue',
              fillOpacity: i.depth * 0.5
            }
          )
        );
      });
      floodOverlayLayerGroup.addTo(map);
    });
}

window.addEventListener("map:init", function (e) {
  var detail = e.detail;
  getFloodOverlays(detail.map);
  detail.map.on('moveend', function() {
    getFloodOverlays(detail.map);
  });
});
