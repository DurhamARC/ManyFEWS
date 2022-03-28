import $ from 'jquery';

var floodOverlayLayerGroup = L.layerGroup();
var currentDay = 0;
var currentHour = 0;

function proportionToColor(proportion, maxHue = 240, minHue = 120) {
  const hue = proportion * (maxHue - minHue) + minHue;
  return `hsl(${hue}, 50%, 30%)`;
}

function getFloodOverlays(map, day, hour) {
  currentDay = day;
  currentHour = hour;
  var bounding_box = map.getBounds();
  var dataUrl = '/depths/' + currentDay + '/'  + currentHour + '/' + bounding_box.getWest() + ',' + bounding_box.getSouth() + ','
    + bounding_box.getEast() + ',' + bounding_box.getNorth();
  fetch(dataUrl)
    .then(function(resp) {
      return resp.json();
    })
    .then(function(data) {
      floodOverlayLayerGroup.clearLayers();
      data["items"].forEach(i => {
        var layer = L.rectangle(i.bounds,
          {
            color: null,
            fillColor: proportionToColor(i.depth/data["max_depth"]),
            fillOpacity: 1 - (i.upper_centile - i.lower_centile)/data["max_depth"]
          }
        );
        layer.bindTooltip(
          "Depth: " + i.depth.toFixed(2) + "m<br>Lower centile: " + i.lower_centile.toFixed(2) +
              "m<br>Upper centile: " + i.upper_centile.toFixed(2) + "m"
        );
        floodOverlayLayerGroup.addLayer(layer);
      });
      floodOverlayLayerGroup.addTo(map);
    });
}

export function initialiseDepthMap() {
  window.addEventListener("map:init", function (e) {
    var detail = e.detail;
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
}

/*window.addEventListener("map:init", function (e) {
  var detail = e.detail;
  getFloodOverlays(detail.map, $(this).attr('data-day'));
  detail.map.on('moveend', function() {
    getFloodOverlays(detail.map, $(this).attr('data-day'));
  });

  $('.daily-risk').click(function(e) {
    getFloodOverlays(detail.map, $(this).attr('data-day'));
    $('.daily-risk').removeClass('current');
    $(this).addClass('current');
  });
  $('.daily-risk').first().addClass('current');
});
*/
