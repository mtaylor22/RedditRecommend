$('#slider').slider({
       min:1,
       max:100,
       value:4,
       slide: function( event, ui ) {
            $( "#amount" ).html(ui.value );
      }});

$('#submit-username').click(function(){
    $('#submit-block').fadeOut(function(){
        $('#loading-block').fadeIn(function(){
            if ($('#recommendation').is(':checked'))
              grabUser($('#user-input').val());
            else if ($('#subreddit').is(':checked'))
                grabSub($('#user-input').val());
            else if ($('#term-b').is(':checked'))
                grabTerm($('#user-input').val());
        });
    });
});
$('#title-block').click(function(){
    $('#loading-block, #statistics-block, #recommendations-block, #subreddit-block, #term-block').fadeOut(function(){
        $('#submit-block').fadeIn();
    });

});
function log(message){
    $('.featured-li').removeClass('featured-li');
    $('#loading-log-list').prepend('<li class=\'featured-li\'>'+message+'</li>');
}

function grabTerm(term){
    log("Grabbing '"+term+"'");
    $.getJSON("/term?term="+term, function(data){
       if (data.success){
            log("Finished '"+term+"'");
            $('#loading-block').slideUp('slow');
            $('#term-block').fadeIn('fast');
           $('.term-name').html(term);
           $('#term-count').html(data.term.total_occurrences);
           $('#term-rank').html(data.term.rank + "/" + data.term.outof);
           $('#term-occurances').html(JSON.stringify(data.term.subreddit_occurrences));
       } else
        alert("Failed to retrieve term");
    });
}

function grabSub(subreddit){
    $('#loading-block').slideDown('fast');
    log("Pulling r/"+subreddit);
    $.getJSON("/sub?subreddit="+subreddit, function (data) {
        if (data.success){
            log("Finished pulling");
            $('#loading-block').slideUp('slow');
            $('#subreddit-block').fadeIn('fast');
            $('.subreddit-name').html(data.subreddit.name);
            $('#link').html('<a href="'+data.subreddit.link+'">'+data.subreddit.name + '</a>');
            $('#subreddit-content').html(data.subreddit.desc);
            $('#terms').html(JSON.stringify(data.subreddit.terms));
        } else{
            alert("Could not retrieve");
        }
    });
}
$('#options-button').click(function(){
   $('#options-panel').slideToggle();
});
function grabUser(user) {
    j = [];
    log("Pulling u/"+user);
//    log("/getRedditor?username="+user+(($('#slider')) ? "&limit="+$('#slider').val(): ""));
    $.getJSON("/getRedditor?username="+user+(($('#slider')) ? "&limit="+$('#slider').slider("option", "value"): ""), function (data) {
        if (data.success) {
            tf = data.redditor.tf;
            df = data.redditor.df;
            subredditCount = data.redditor.sub_count;
            log("Got User");
            $.getJSON("/processRedditor?tf="+JSON.stringify(tf)+"&df="+JSON.stringify(df)+"&subredditCount="+JSON.stringify(subredditCount), function (data) {
                if (data.success){
                    var tfidf = data.data.tfidf;
                    cosine = {};
                    tc = 0;
                    for (var t in tfidf) {
                        if (tfidf.hasOwnProperty(t)) {
                            tc++;
                        }
                    }
                    actual_count = 0;
                    for (var term in tfidf) {
                        if (tfidf.hasOwnProperty(term)) {
                            log("Started on '" + term + "'");
                            (function(term) {
                                $.ajax({
                                    url: "/processTerm?tfidf=" + JSON.stringify(tfidf) + "&post=" + term + "&cosine=" + JSON.stringify({}),
                                    dataType: 'json',
                                    async: true,
                                    success: function (data) {
                                        if (data.success) {
                                            log("Finished '" + term + "'");
                                            cosine = mergeObjects(cosine, data.data);
//                                                    j.push(data.data);
                                        }
                                        actual_count++;
                                        if (actual_count == tc) {

                                            log('Removing sparse subreddits');
                                            $('#status').append("Done!");
                                            var sortable = [];
                                            for (var c in cosine)
                                                if (cosine.hasOwnProperty(c))
                                                    sortable.push([c, cosine[c]]);
                                            sortable.sort(function (a, b) {
                                                return b[1] - a[1]
                                            });

//                                            $('#list').html(JSON.stringify(sortable));
                                            $('#results-table').html('<tr><td>Rank</td><td>Subreddit</td><td>Score</td></tr>');
                                            var added = 0;
                                            var totalAdded = 0;
                                            for (var j = 0; j < 40; j++) {
                                                $.getJSON('/sub?subreddit='+sortable[j][0], function(data){
                                                    totalAdded++;
                                                    if (data.subreddit.terms.length > 4) {
                                                        var i = added++;
                                                        console.info(data.subreddit.terms.length);
                                                        $('#stat-comment-num').html(i);
                                                        $('#results-table').append('<tr><td><div class="index">' + (i + 1) + '.</div></td><td><a href="http://www.reddit.com/r/' + data.subreddit.name + '">reddit.com/r/' + data.subreddit.name + '</a></td><td><div class="score">' + Math.round(sortable[i][1] / 1 * 10000) / 100 + '%.</div></td></tr>');
                                                        if (added > 20 || totalAdded == 40 && $('#recommendations-block').css('display') == 'none'){
                                                            log("Done!");
                                                            $('#recommendations-block, #statistics-block').fadeIn();
                                                            $('#loading-block').slideUp('slow');
                                                        }
                                                    }
                                                });

                                            }
                                        }

                                    }
                                });
                            })(term);
                        }
                    }

                } else {
                    alert("failed to process user data");
                }
            });
        } else {
            alert("failed to get user");
        }
    });
}
function mergeObjects(a,b) {
    var c = {};
    for (var term in a) {
        if (a.hasOwnProperty(term)) {
            c[term ]= a[term]
        }
    }
    for (var t2 in b) {
        if (b.hasOwnProperty(t2)) {
            c[t2] = (a[t2] != undefined)? c[t2]+ b[t2] : b[t2]
        }
    }
    return c;
}
