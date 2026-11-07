Create a new tooling called Regression analysis, but document the complete architecture and structure, this will be used later by another AI model to recreate the tooling, the documentation need to be flawless.

Requirements:
1. The tooling receives either  reference baseline  patch id, release name and failing test information, where the failing test data is as follows

    Scenario Name: String
    Machine Type: String 
    Test Configuration: String 
    Test Case name: String

    Reference Baseline: String
    Patch ID: String 
    Release Name: String

2. The tooling need to connect to gh repository and checkout the repo, it will use files given below format
    - File Extenstions will be json or yaml (recommed which one to use)
    - File names will be like FC-<ddd> where d is digit
    - Files will contain extries as follows

    Function Cluster: FC-<ddd>

    Failing Test Gap Identification: (a section)

    Component: ( a section)
        Test Entry: (one of many sections)


            Test Scenario Name: <String> , this need to be always specified mandatory field
            Configuration Name: <String> : Optional Field
            Machine Type: <String> : Optional Field
            Test Case Name: <String> : Optional Field

            Gap Specification : <String> ( can be multiple lines of string where the gap due to this failing test is specified)

            Mitigations :<String> ( can be multiple lines of string where the motogations of coverage gap  risks due to this failing test is specified) This is an optional field

            Tags: [String] List of strings to give tags optional field
            
            Baselines : [String] Can be List of baselines or, a range specifying baselines where baseline format will be <prefix>_<DataTimeTag>_<HHMMSS>, and range will be like an entry to list [range:<prefix>_261021_125411 - <prefix>_261101_101145, <prefix>_261027_115411, ...], where range has keyword range: before.

            Release: <String> Mandatory

            PatchIDs: [String] List of Patch IDs

            Remarks: [String]: Can be Multiline String

            output_dir: [Path] Can be both relative or full path tool need to resolve




2.1. Following fields can contain full or partial wildcard (*)
            Test Scenario Name: 
            Configuration Name: 
            Machine Type: 
            Test Case Name: 
2.2 : The Test Enrties are listed in relevant component name, however component is just a container has no functional impact
2.3: The Test Entry should have at least one of Reference Baseline List or Patch ID list non empty or specified, if all missing this is a syntax error, imcomplete, however they can co-exists.

Functional Requirements:

3. The tool need to read environmental variable ${GH_PAT} and use it to access the Git Repo, 
4. The Tool need to have a configuration yaml or toml file (you recommend) to read the GitHub Repo Information and Branch Information
    For testing purposes use this repo 
5. The tool should checkout the branch of the repo, and read all the Gap Sepcifications in {RepoRoot}\TestFailureGapSpec
6. Tool will receive following inputs 

    a. the Failing Test Data (will be a list of dictionaries) as specified above in 2.1 as     
            Test Scenario Name: 
            Configuration Name: 
            Machine Type: 
            Test Case Name: 
    b. Reference Baseline data and/or Patch ID
    c. Release Name
7. The tool check all the files and will find the matching entries with inputs,
7.1 Since Wildcards can be used it will detect the most specific matching entries and use those
7.2 the tool will store both mathced and unmatched inputs 

8. An HTML, JSON and MD report will be generated with the matches and unmatched inputs where the inputs for release, Reference Baseline and/or Patch ID will be reported at the top of the report. Also report need to use the version of the document, where please recommed a way for versioning 

8.1 The generaed reports will be stored in <output_dir>
8.2 Generated report should for each detected entry create a table and report all the relevant information.
8.3 For unmatched inputs of test data a table need to list with following columns of unmatched inputs
                Test Scenario Name: 
            Configuration Name: 
            Machine Type: 
            Test Case Name: 



