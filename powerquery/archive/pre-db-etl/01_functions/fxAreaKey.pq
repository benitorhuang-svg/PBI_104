(location as record) as text =>
    Text.Combine(
        {
            if location[jobAddrNo] = null then "" else Text.From(location[jobAddrNo], "en-US"),
            if location[jobAddrNoDesc] = null then "" else location[jobAddrNoDesc],
            if location[jobAddress] = null then "" else location[jobAddress],
            if location[lat] = null then "" else Number.ToText(location[lat], "G", "en-US"),
            if location[lon] = null then "" else Number.ToText(location[lon], "G", "en-US")
        },
        "|"
    )
