
''' Just a playground for exploring the characteristics of using ZeroRPC/gevent for worker tasking and execution. '''

import zerorpc
import gevent.monkey
gevent.monkey.patch_all(thread=False) # Monkey!
import logging
logging.basicConfig()
import datetime
import StringIO
import json
import hashlib

''' Add bro to path for bro_log_reader '''
import os
os.sys.path.insert(0, os.path.join(os.getcwd(),'workers/bro'))

# Local modules
try:
    from . import data_store
    from . import els_indexer
    from . import neo_db
    from . import plugin_manager
    from . import bro_log_reader
except ValueError:
    import data_store
    import els_indexer
    import neo_db
    import plugin_manager
    import bro_log_reader

class WorkBench():
    ''' Just a playground for exploring the characteristics of using ZeroRPC/gevent for worker tasking and execution. '''
    def __init__(self, store_uri=None, els_hosts=None, neo_uri=None):

        # Open DataStore
        self.data_store = data_store.DataStore(**{'uri': store_uri} if store_uri else {})

        # ELS Indexer
        self.indexer = els_indexer.ELS_Indexer(**{'hosts': els_hosts} if els_hosts else {})

        # Neo4j DB
        self.neo_db = neo_db.NeoDB(**{'uri': neo_uri} if neo_uri else {})

        # Create Plugin Grabber
        self.plugin_meta = {}
        plugin_manager.PluginManager(self._new_plugin)

    # Data storage methods
    def store_sample(self, filename, input_bytes, type_tag):
        ''' Store a sample into the DataStore. '''
        return self.data_store.store_sample(filename, input_bytes, type_tag)

    def get_sample(self, md5_or_filename):
        ''' Get a sample from the DataStore. '''
        sample = self.data_store.get_sample(md5_or_filename)
        return {'sample': sample} if sample else None

    def have_sample(self, md5_or_filename):
        ''' Do we have this sample in the DataStore. '''
        return self.data_store.have_sample(md5_or_filename)

    @zerorpc.stream
    def stream_sample(self, md5_or_filename, max_rows):
        ''' Stream the sample by giving back a generator '''

        # Grab the sample and it's raw bytes
        sample = self.data_store.get_sample(md5_or_filename)
        raw_bytes = sample['raw_bytes']

        # Figure out the type of file to be streamed
        type_tag = sample['type_tag']
        if type_tag == 'bro':
            bro_log = bro_log_reader.BroLogReader(convert_datetimes=False)
            mem_file = StringIO.StringIO(raw_bytes)
            generator = bro_log.read_log(mem_file, max_rows=max_rows)
            return generator
        elif type_tag == 'els_query':
            els_log = json.loads(raw_bytes)
            # Try to determine a couple of different types of ELS query results
            if 'fields' in els_log['hits']['hits'][0]:
                generator = (row['fields'] for row in els_log['hits']['hits'][:max_rows])
            else:
                generator = (row['_source'] for row in els_log['hits']['hits'][:max_rows])
            return generator
        elif type_tag == 'log':
            generator = ({'row':row} for row in raw_bytes.split('\n')[:max_rows])
            return generator
        elif type_tag == 'json':
            generator = (row for row in json.loads(raw_bytes)[:max_rows])
            return generator
        else:
            raise Exception('Cannot stream file %s with type_tag:%s' % (md5_or_filename, type_tag))

    # Index methods
    def els_index_sample(self, md5, index_name):
        ''' Index a stored sample with the Indexer '''
        generator = self.stream_sample(md5, None)
        for row in generator:
            self.indexer.index_data(row, index_name)

    def index_worker_output(self, worker_class, md5, index_name):
        ''' Index worker output with Indexer'''

        # Grab the data
        data = self.work_request(worker_class, md5)[worker_class]

        # Okay now index the data
        self.indexer.index_data(data, index_name=index_name, doc_type='unknown')

    def search(self, index_name, query):
        ''' Search an index'''
        return self.indexer.search(index_name, query)


    # Make a work request for an existing stored sample
    def work_request(self, worker_class, md5, subkey=None):
        ''' Make a work request for an existing stored sample '''

        # Check valid
        if worker_class not in self.plugin_meta.keys():
            raise Exception('Invalid work request for class %s (not found)' % (worker_class))

        # Get results (even if we have to wait for them)
        # Note: Yes, we're going to wait. Gevent concurrent execution will mean this
        #       code gets spawned off and new requests can be handled without issue.
        work_results = self._recursive_work_resolver(worker_class, md5)

        # Subkey?
        if subkey:
            work_results = work_results[worker_class]
            for key in subkey.split('.'):
                work_results = work_results[key]

        # Clean it and ship it
        work_results = self.data_store.clean_for_serialization(work_results)
        return work_results

    def batch_work_request(self, worker_class, md5_list=None, subkey=None):
        ''' Make a batch work request for an existing set of stored samples.
            The md5_list arg can be set to a list of md5s or left as None and
            all of the samples will receive this work request. '''
        if not md5_list:
            md5_list = self.data_store.all_sample_md5s()
        if subkey:
            return [self.work_request(worker_class, md5, subkey) for md5 in md5_list]
        else:
            return [self.work_request(worker_class, md5)[worker_class] for md5 in md5_list]

    def worker_info(self):
        ''' List the current worker plugins. '''
        return {plugin['name']:plugin['description'] for name, plugin in self.plugin_meta.iteritems()}

    def get_datastore_uri(self):
        ''' Gives you the current datastore URL '''
        return self.data_store.get_uri()

    def set_datastore_uri(self, uri):
        ''' Sets the datastore URL. Note: Don't use this unless you know what you're doing. '''
        self.data_store = data_store.DataStore(uri)

    def _new_plugin(self, plugin):
        ''' The method handles the mechanics around new plugins. '''
        print '< %s: loaded >' % (plugin['name'])
        plugin['time_stamp'] = datetime.datetime.utcnow()
        self.plugin_meta[plugin['name']] = plugin

    def _store_work_results(self, results, collection, md5):
        self.data_store.store_work_results(results, collection, md5)
    def _get_work_results(self, collection, md5):
        results = self.data_store.get_work_results(collection, md5)
        return {collection: results} if results else None


    # So the trick here is that since each worker just stores it's input dependencies
    # we can resursively backtrack and all the needed work gets done.
    def _recursive_work_resolver(self, worker_class, md5):

        # Looking for the sample?
        if (worker_class == 'sample'):
            return self.get_sample(md5)

        # Do I actually have this plugin? (might have failed, etc)
        if (worker_class not in self.plugin_meta):
            print 'Request for non-existing or failed plugin: %s' % (worker_class)
            return {}

        # If the results exist and the time_stamp is newer than the plugin's, I'm done
        collection = self.plugin_meta[worker_class]['name']
        work_results = self._get_work_results(collection, md5)
        if work_results:
            if self.plugin_meta[worker_class]['time_stamp'] < work_results[collection]['__time_stamp']:
                print 'Returning cached work results for plugin: %s' % (worker_class)
                return work_results
            else:
                print 'Updating work results for new plugin: %s' % (worker_class)

        dependencies = self.plugin_meta[worker_class]['dependencies']
        dependant_results = {}
        for dependency in dependencies:
            dependant_results.update(self._recursive_work_resolver(dependency, md5))
        print 'New work for plugin: %s' % (worker_class)
        work_results = self.plugin_meta[worker_class]['handler']().execute(dependant_results)

        # Store the results and return
        self._store_work_results(work_results, collection, md5)
        return self._get_work_results(collection, md5)

    def _find_element(self,d,k):
        if k in d: return d[k]
        submatch = [d[_k][k] for _k in d if k in d[_k]]
        return submatch[0] if submatch else None

def main():
    import os
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-db', '--database', type=str, default='workbench', help='database used by workbench server')
    args = parser.parse_args()


    # Spin up Workbench ZeroRPC
    database = args.database
    print 'ZeroRPC %s' % ('tcp://0.0.0.0:4242')
    s = zerorpc.Server(WorkBench(store_uri='mongodb://localhost/'+database), name='workbench')
    s.bind('tcp://0.0.0.0:4242')
    s.run()

if __name__ == '__main__':
    main()
