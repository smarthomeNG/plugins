
function build_item_subtree_recursive(data) {
    var result = [];
    var tree_element = {};
    tree_element['text'] = data.path;
    var node_length = data.nodes.length;
    if (data.nodes.length > 0) {
        var child_nodes = [];
        for (var i = 0; i < node_length; i++) {
            var new_child_node = build_item_subtree_recursive(data.nodes[i]);
            child_nodes.push(new_child_node);
        }
        tree_element['tags'] = data.tags;
        tree_element['nodes'] = child_nodes;
    }

    return tree_element;
}

function reload(data) {
    if (data) {
        $('#refresh-element').addClass('fa-spin');
        $('#reload-element').addClass('fa-spin');
        $('#cardOverlay').show();
        $.getJSON('item_detail_json.html?item_path='+data.text, function(result) {
            getDetailInfo(result);
            window.setTimeout(function(){
                $('#refresh-element').removeClass('fa-spin');
                $('#reload-element').removeClass('fa-spin');
                $('#cardOverlay').hide();
            }, 500);

        });
    }
}

var selectedNode;

function getTree() {
    var item_tree = [];

    $.getJSON('items.json?mode=tree', function(result) {
        $.each(result, function(index, element) {
            item_tree.push(build_item_subtree_recursive(element));
        });
        $('#tree').treeview({
            data: item_tree,
			levels: 1,
            showTags: true,
            onNodeSelected: function(event, node) {
                selectedNode = node;
                reload(node);
            }
        });
    });

    var search = function(e) {
          results = [];
          var pattern = $('#input-search').val();
          var options = {
            ignoreCase: true,
            exactMatch: false,
            revealResults: true
          };
          var results = $('#tree').treeview('search', [ pattern, options ]);
          $('#search-results').html(' - Treffer: '+results.length);
          $('#btn-clear-search').on('click', function (e) {
            $('#tree').treeview('clearSearch');
            $('#tree').treeview('collapseAll', { silent: false });
            $('#input-search').val('');
            $('#search-output').html('');
            results = [];
            $('#search-results').html('');
          });
    }
    if ($('#input-search').val() != '') {
        changeSearchButtonColor(true);
    }
    $('#btn-search').on('click', search);
    $("#input-search").keypress(function(event){
        if(event.keyCode == 13){
            $("#btn-search").click();
        }
    });

    // Expand/collapse all
    $('#btn-expand-all').on('click', function (e) {
      $('#tree').treeview('expandAll', { silent: false });
    });
    $('#btn-collapse-all').on('click', function (e) {
      $('#tree').treeview('collapseAll', { silent: false });
    });
}