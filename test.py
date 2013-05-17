from pyscanner import PyScanner


def test():
    ps = PyScanner()
    results = ps.search('paris', 'new york', '06/06/2013', '07/07/2013')
    for r in results:
        print(r.agent, r.price, r.link)

if __name__ == '__main__':
    test()
