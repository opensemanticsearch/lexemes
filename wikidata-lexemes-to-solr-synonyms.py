#!/usr/bin/python3
# -*- coding: utf-8 -*-

import requests
import json
from SPARQLWrapper import SPARQLWrapper, XML, JSON

#
# Generate Solr synonyms graph filter resource config from lexemes (f.e. OpenData from Wikidata)
#

class lexemes2solr(object):

	dictionary = {}

	def __init__(self):
	
		self.verbose = True
                
		self.solr = "http://localhost:8983/solr/"
		self.solr_core = "core1"
		self.solr_managed_synonyms_resource = "lexemes"
		
		self.sparql_endpoint = 'https://query.wikidata.org/sparql'
		
		self.language = 'en'
		
		# Todo: If got not listed language code as command line option instead of language entity URI, ask Wikidata by SELECT ?s WHERE {  ?s wdt:P218 'languagecode'. }		
		self.langugages = { 'en': 'http://www.wikidata.org/entity/Q1860',
							'de': 'http://www.wikidata.org/entity/Q188',
							'es': 'http://www.wikidata.org/entity/Q1321',
							'pt': 'http://www.wikidata.org/entity/Q5146',
							'hu': 'http://www.wikidata.org/entity/Q9067',
		}
		
	#
	# safe the dictionary of synonyms by Solr REST API for managed resources
	#
	def synonyms2solr(self):
		url = self.solr
		if not url.endswith('/'):
			url += '/'
		url += self.solr_core + '/schema/analysis/synonyms/' + self.solr_managed_synonyms_resource
		headers = {'content-type' : 'application/json'}
		
		r = requests.post(url=url, data=json.dumps(self.dictionary), headers=headers)
				

	#
	# get lemmas and lexicalform entries for given language from Wikidata, convert to dictionary and safe to Solr
	#
	def process(self):

		# get wikidata entity URI for language from preconfigured mappings, if got language code instead full wikidata URI as language selection
		language_entity = self.language
		if language_entity in self.langugages:
			language_entity = self.langugages[language_entity]
			
		# build SPARQL query
		query = """

SELECT DISTINCT ?lemma ?representation WHERE
{ 

 ?LexicalEntry rdf:type <http://www.w3.org/ns/lemon/ontolex#LexicalEntry>.
 ?LexicalEntry <http://purl.org/dc/terms/language> <""" + language_entity + """>.

 ?LexicalEntry wikibase:lemma ?lemma.

 ?LexicalEntry <http://www.w3.org/ns/lemon/ontolex#lexicalForm> ?LexicalFormEntry.
 ?LexicalFormEntry <http://www.w3.org/ns/lemon/ontolex#representation> ?representation.

}
"""

		# read query results from SPARQL endpoint
		sparql = SPARQLWrapper(self.sparql_endpoint)
		sparql.setQuery(query)
		sparql.setReturnFormat(JSON)
		results = sparql.query().convert()

		count_lemmas = 0
		count_representations = 0
		
		# Read lemmas and represations from SPARQL result to dictionary {lemma: [representations]}
		for result in results["results"]["bindings"]:
	
			lemma =  result["lemma"]["value"]
			representation = result["representation"]["value"]

			# skip, if lemma same as representation, so no need for synonym config for this entry
			if lemma != representation:

		        # create dictionary entry for lemma
				if not lemma in self.dictionary:
            		# add lemma itself as synonym, so Solr Synonyms Graph resolution includes original concept/lemma, too, not only rewritten to synonym(s)
					self.dictionary[lemma] = [lemma]
					count_lemmas += 1

				self.dictionary[lemma].append(representation)
				count_representations += 1


		# subconnect multiple lexical forms: connect the lexical forms as synonym for each other, too, not only to the lemma

		extended_dictionary = self.dictionary.copy()
		
		for lemma in self.dictionary:

			for representation in self.dictionary[lemma]:

				if not representation in extended_dictionary:
					extended_dictionary[representation] = [representation]
				
				for otherrepresentation in self.dictionary[lemma]:
					if not otherrepresentation in extended_dictionary[representation]:
						extended_dictionary[representation].append(otherrepresentation)

		self.dictionary = extended_dictionary

		# write the synonyms (collected in dictionary) to Solr at once (better performance, since the json config has only to be rewritten once)
		self.synonyms2solr()

		# output stats
		if self.verbose:
			print ("Imported {} lemmas and their {} (different) representations".format(count_lemmas, count_representations))


# start by command line
if __name__ == "__main__":

	from optparse import OptionParser

	parser = OptionParser("wikidata-lexemes-to-solr-synonyms [options]")

	parser.add_option("-s", "--solr", dest="solr", default='http://localhost:8983/solr/', help="Solr URI like http://localhost:8983/solr/")
	parser.add_option("-c", "--core", dest="core", default='core1', help="Solr core/index name")
	parser.add_option("-r", "--resource", dest="resource", default='lexemes', help="Solr managed synonyms resource where to store the results")
	parser.add_option("-l", "--language", dest="language", default='en', help="Language (Wikidata entity)")
	
	(options, args) = parser.parse_args()


	converter = lexemes2solr()
	
	converter.language = options.language
	converter.solr = options.solr
	converter.solr_core = options.core
	converter.solr_managed_synonyms_resource = options.resource

	converter.process()
