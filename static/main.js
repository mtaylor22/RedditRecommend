$('#submit-username').click(function(){
    $('#submit-block').fadeOut(function(){
        $('#loading-block').fadeIn(function(){
            $.getJSON( "/user", {'username':$('#user-input').val()}, function( data ) {
                if (data.success) {
                    $('#loading-block').fadeOut(function () {
                        $('#recommendations-block, #statistics-block').fadeIn();
                        $('#stat-comment-num').html(data.redditor.num);
                    });
                    redditor = data.redditor;
                } else {
                    alert("error");
                }
            });
        });
    });
});
$('#title-block').click(function(){
    $('#loading-block, #statistics-block, #recommendations-block').fadeOut(function(){
        $('#submit-block').fadeIn();
    });

});