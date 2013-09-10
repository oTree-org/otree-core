function partial(func /*, 0..n args */) {
  var args = Array.prototype.slice.call(arguments, 1);
  return function() {
    var allArguments = args.concat(Array.prototype.slice.call(arguments));
    return func.apply(this, allArguments);
  };
}

function sendEyeInfo(direction)
{
	var id = $(this).attr('id');
	var data = {id:id, direction:direction};
	var args = {type:"POST", url:"/eye_tracking_info/", data:data};    
	$.ajax(args);
}

function sendEyeInfoOver()
{
    return sendEyeInfo("over");
}

function sendEyeInfoOut()
{
    return sendEyeInfo("out");
}