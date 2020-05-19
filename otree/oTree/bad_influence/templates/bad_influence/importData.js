function importData ()
{
    d3.json("faces.json", function(data)
        {
            console.log(data);
        }
    )
}