(function($) {
  $(function() {
    // 仅在「新增 Class notice」页面才生效
    if (!/\/classnotice\/add\/?$/.test(window.location.pathname)) {
      return;
    }

    var $slot = $('#id_course_slot');
    var $sub  = $('#id_sub_group');
    var url   = $sub.data('url');    // 从 widget attrs 里读 data-url

    if (!$slot.length || !$sub.length || !url) {
      return;
    }

    // 选中 slot 时，AJAX 拉小班列表填充到 sub_group
    function loadSubgroups() {
      var slotId = $slot.val();
      // 禁用下拉，直至数据回来
      $sub.prop('disabled', true).html('<option>Loading…</option>');

      $.ajax({
        url: url,
        data: { slot_id: slotId },
        success: function(resp) {
          var html = '<option value="">---------</option>';
          resp.results.forEach(function(item) {
            html += '<option value="' + item.id + '">' + item.label + '</option>';
          });
          $sub.html(html).prop('disabled', false);
        },
        error: function() {
          // 失败时恢复空状态
          $sub.html('<option value="">---------</option>').prop('disabled', false);
        }
      });
    }

    // select2 选中／清除，也捕捉原生 change
    $slot
      .on('select2:select', loadSubgroups)
      .on('select2:clear',  loadSubgroups)
      .on('change',         loadSubgroups);
  });
})(django && django.jQuery || window.jQuery);
