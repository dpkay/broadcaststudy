function foo(button) {
  $.ajax({
    url: 'rpc',
    data: JSON.stringify({
      "action": "vote",
      "key": button.attr("name"),
      "value": button.val()
    }),
    cache: false,
    contentType: false,
    processData: false,
    type: 'POST',
    success: function(data) {
      var result = $.parseJSON(data);
      var status = result["status"];
      var tableRow = button.parent().parent();
      var questionRowName = 'question_' + button.attr('name');
      //alert(questionRowName);
      var questionRow = $('#' + questionRowName);
      if (status == "stored") {
        tableRow.addClass('completed');
        questionRow.addClass('completed');
      } else {
        tableRow.removeClass('completed');
        questionRow.removeClass('completed');
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
  //alert(num_completed);
}
