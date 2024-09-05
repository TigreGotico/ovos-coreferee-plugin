from setuptools import setup


PLUGIN_ENTRY_POINT = 'ovos-coreferee-plugin=ovos_coreferee.opm:CorefereeSolver'
UTTERANCE_ENTRY_POINT = (
    'ovos-utterance-coreferee-normalizer=ovos_coreferee.opm:CorefereeNormalizerPlugin'
)
setup(
    name='ovos-coreferee-plugin',
    version='0.1.0',
    packages=['ovos_coreferee'],
    url='https://github.com/TigreGotico/ovos-coreferee-plugin',
    license='apache-2.0',
    author='jarbasAi',
    install_requires=["spacy",
                      "coreferee",
                      "ovos-plugin-manager"],
    include_package_data=True,
    author_email='jarbasai@mailfence.com',
    description='OVOS coreference solver',
    entry_points={
        'intentbox.coreference': PLUGIN_ENTRY_POINT,
        'neon.plugin.text': UTTERANCE_ENTRY_POINT
    }
)
