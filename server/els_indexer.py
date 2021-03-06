
''' ELS_Indexer class for WorkBench '''
import hashlib
import StringIO

class ELS_Indexer():

    def __init__(self, hosts=[{"host": "localhost", "port": 9200}]):

        # Get connection to ElasticSearch
        try:
            self.es = elasticsearch.Elasticsearch(hosts)
            print 'ELS Indexer connected: %s' % (str(hosts))
        except:
            print 'ELS connection failed! Is your ELS server running?'
            exit(1)

    def index_data(self, data, index_name='meta', doc_type='unknown'):

        # Index the data (which needs to be a dict/object) if it's not
        # we're going to toss an exception
        if not isinstance(data, dict):
            raise Exception('Index failed, data needs to be a dict!')

        try:
            self.es.index(index=index_name, doc_type=doc_type, body=data)
        except Exception, error:
            print 'Index failed: %s' % str(error)
            # raise Exception('Index failed: %s' % str(error))

    def search(self, index_name, query):
        return self.es.search(index=index_name, body=query)

class ELS_StubIndexer():

    def __init__(self, hosts=[{"host": "localhost", "port": 9200}]):
        print 'ELS Stub Indexer connected: %s' % (str(hosts))
        print 'Install ElasticSearch and python bindings for ELS indexer. See README.md'

    def index_data(self, data, index_name='meta', doc_type='unknown'):
        print 'ELS Stub Indexer getting called...'

    def search(self, index_name, query):
        print 'ELS Stub Indexer getting called...'

try:
    import elasticsearch
    ELS_Indexer = ELS_Indexer
except ImportError:
    ELS_Indexer = ELS_StubIndexer