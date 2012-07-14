function doVote(button, action) {
  var ajaxData = JSON.stringify({
      "action": action,
      "key": button.attr("name"),
      "value": button.val()
    });

  $.ajax({
    url: 'rpc',
    data: ajaxData,
    cache: false,
    contentType: false,
    processData: false,
    type: 'POST',
    success: function(data) {
      var result = $.parseJSON(data);
      var status = result["status"];
      var tableRow = button.parent().parent();
      var questionRowName = 'question_' + button.attr('name');
      var questionRow = $('#' + questionRowName);
      
      var splitName = button.attr('name').split('_'); 
      var prefix = splitName[0];
      var suffix = splitName[1];
      //var oppositeSuffix = suffix=="best" ? "worst" : "best";
      //var opposite = $('#'+prefix+'_'+oppositeSuffix+'_'+button.attr('value'));
      if (status == "stored") {
        tableRow.addClass('completed');
        questionRow.addClass('completed');
      } else {
        tableRow.removeClass('completed');
        questionRow.removeClass('completed');
      }
      if (status == "failed") {
        oldId = button.attr('name')+'_'+result['oldValue'];
        $('#' + oldId).attr("checked", "checked");
        tableRow.addClass('failed');
        questionRow.addClass('failed');
        setTimeout(function() {
          tableRow.removeClass('failed');
          questionRow.removeClass('failed');
          if(result['oldValue']>0) {
            tableRow.addClass('completed');
            questionRow.addClass('completed');
          }
        }, 250);
      } else {
        tableRow.removeClass('failed');
        questionRow.removeClass('failed');
      }
      updateCount();
    }
  });
}

function updateCount() {
  var buttonRows = $('tr').filter($('.button-row'));
  var num_completed = buttonRows.filter($('.completed')).length;
  var num_total = buttonRows.filter($('.button-row')).length;
  var percentage = Math.round(num_completed/num_total*100);
  $('#completedcount').text(num_completed);
  $('#totalcount').text(num_total);
  $('#percentage').text(percentage+"%");
}

function playAll(ids) {
  window.cuedIds = [];
  for (var i=0; i<ids.length; i++) {
    var id = ids[i];
    var containerName = ids[i] + "_container";
    var player = YoutubePlayer.findById(containerName);
    if(!player) {
      var player = new YoutubePlayer(containerName, ids[i], {
        width: 320,
        height: 205 });

      player.on('cued', function(eventName, videoId) {
        window.cuedIds.push(videoId);
        if(window.cuedIds.length == 3) {
          for (var i=0; i<3; i++) {
            var player = document.getElementById(cuedIds[i] + "_container");
            player.playVideo();
          }
        }
      });
    } else {
      player.ref.seekTo(0);
      player.ref.playVideo();
    } 
  }
}

