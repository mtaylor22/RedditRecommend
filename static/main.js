$('#submit-username').click(function(){
    $('#submit-block').fadeOut(function(){
        $('#loading-block').fadeIn(function(){
            window.setTimeout(function(){
                $('#loading-block').fadeOut(function(){
                    $('#recommendations-block, #statistics-block').fadeIn();
                });
            }, 500);
        });
    });
});
$('#title-block').click(function(){
    $('#loading-block, #statistics-block, #recommendations-block').fadeOut(function(){
        $('#submit-block').fadeIn();
    });

});