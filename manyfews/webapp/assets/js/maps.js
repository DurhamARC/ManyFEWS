import $ from 'jquery';
import './bing.js';

var floodOverlayLayerGroup = L.layerGroup();
var currentDay = 0;


function getFloodOverlays(map, day) {
  currentDay = day;
  var bounding_box = map.getBounds();
  var dataUrl = '/depths/' + currentDay + '/' + bounding_box.getSouth() + ',' + bounding_box.getWest() + ','
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
  var mapApiKey = $('#mapApiKey').val();
  var bing = new L.BingLayer(mapApiKey);
  detail.map.addLayer(bing);
  getFloodOverlays(detail.map, currentDay);
  detail.map.on('moveend', function() {
    getFloodOverlays(detail.map, currentDay);
  });

  $('.daily-risk').click(function(e) {
    getFloodOverlays(detail.map, $(this).attr('data-day'));
    $('.daily-risk').removeClass('current');
    $(this).addClass('current');
  });
  $('.daily-risk').first().addClass('current');
});
