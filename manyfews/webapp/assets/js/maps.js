import $ from 'jquery';
import './bing.js';

var floodOverlayLayerGroup = L.layerGroup();
var currentDay = 0;
var currentHour = 0;


function getFloodOverlays(map, day, hour) {
  currentDay = day;
  currentHour = hour;
  var bounding_box = map.getBounds();
  var dataUrl = '/depths/' + currentDay + '/'  + currentHour + '/' + bounding_box.getSouth() + ',' + bounding_box.getWest() + ','
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
  getFloodOverlays(detail.map, currentDay, currentHour);
  detail.map.on('moveend', function() {
    getFloodOverlays(detail.map, currentDay, currentHour);
  });

  $('.risk').click(function(e) {
    getFloodOverlays(detail.map, $(this).attr('data-day'), $(this).attr('data-hour'));
    $('.risk').removeClass('current');
    $(this).addClass('current');
  });
  $('.risk').first().addClass('current');
});
