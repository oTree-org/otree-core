(function ($) {
    /*
     * jQuery plugin - katex
     *
     * Call $(...).katex() to render the text inside the matched elements with
     * the katex library to HTML.
     */
    $.fn.katex = function () {
        return $(this).each(function () {
            var expr;
            if ($(this).attr('latex-src') !== undefined) {
                expr = $(this).attr('latex-src');
            } else {
                expr = $(this).text();
            }

            $(this).attr('latex-src', expr);
            katex.render(expr, this);
            return this;
        });
    };

    $(document).ready(function () {
        $('.latex').katex();
    });
})(jQuery);
