jQuery(document).ready(function () {
    jQuery('button.btn.btn-primary:contains("Generate")').on('click', function () {
        $('.flash-messages').children().alert('close');
    });
});