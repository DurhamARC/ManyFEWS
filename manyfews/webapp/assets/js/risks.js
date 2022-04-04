import $ from 'jquery';
import { Tooltip } from 'bootstrap';
import { interpolateOrRd } from 'd3-scale-chromatic';

export function initialiseDailyRisks() {
  $(document).ready(function(){
    $('.risk').each(function() {
      var risk = $(this).attr('data-risk');
      $(this).css('background-color', interpolateOrRd(risk));
      if (risk >= 0.7) {
        $(this).css('color', 'white');
      }
      new Tooltip(this);
    });
  });
};
