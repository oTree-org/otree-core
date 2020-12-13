def prepare_for_termination(PORT) -> int:
    # expensive imports. do it in here so that we don't delay devserver_inner
    from urllib.request import urlopen
    import urllib.error

    try:
        # send data= so it makes a post request
        # it seems using localhost is very slow compared to 127.0.0.1
        resp = urlopen(f'http://127.0.0.1:{PORT}/SaveDB/', data=b'foo')
        return int(resp.read().decode('utf-8'))
    except urllib.error.URLError as exc:
        # - URLError may happen if the server didn't even start up yet
        #  (if you stop it right away)
        pass
