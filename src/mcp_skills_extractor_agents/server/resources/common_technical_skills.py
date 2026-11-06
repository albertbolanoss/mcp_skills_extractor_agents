"""MCP resource: canonical IT technical-skill taxonomy.

A single, shared vocabulary of IT technical skills — grouped by category, each
mapped to the alternate spellings/abbreviations it's commonly found under in a
resume or job posting. Extraction tools/agents use it to normalize whatever
raw text they find (e.g. "JS", "ReactJS", "Postgres") to one canonical name
(e.g. "JavaScript", "React", "PostgreSQL"), so every agent in the pipeline
stores and reports skills in the same unified language instead of each one
inventing its own spelling.
"""

from ..mcp_server import mcp

COMMON_TECHNICAL_SKILLS: dict[str, dict[str, list[str]]] = {
    "programming_languages": {
        "Python": ["Python3", "Python 3"],
        "Java": ["Java SE", "Java EE", "J2EE"],
        "JavaScript": ["JS", "ECMAScript", "ES6", "ES2015"],
        "TypeScript": ["TS"],
        "C#": ["CSharp", "C Sharp"],
        "C++": ["Cpp", "C Plus Plus"],
        "C": ["ANSI C"],
        "Go": ["Golang"],
        "Rust": [],
        "Ruby": [],
        "PHP": [],
        "Kotlin": [],
        "Swift": [],
        "Scala": [],
        "R": ["R Language"],
        "SQL": ["Structured Query Language"],
        "Bash": ["Shell Scripting", "Shell", "sh"],
        "PowerShell": [],
        "Perl": [],
        "MATLAB": [],
        "Objective-C": ["ObjC"],
        "Dart": [],
        "Haskell": [],
        "Lua": [],
        "Groovy": [],
        "VB.NET": ["Visual Basic .NET", "Visual Basic"],
        "COBOL": [],
        "Elixir": [],
        "Clojure": [],
    },
    "frontend_technologies": {
        "HTML": ["HTML5"],
        "CSS": ["CSS3"],
        "Sass": ["SCSS"],
        "Less": [],
        "React": ["React.js", "ReactJS"],
        "Angular": ["AngularJS", "Angular 2+"],
        "Vue.js": ["Vue", "VueJS"],
        "Svelte": [],
        "jQuery": [],
        "Next.js": ["NextJS"],
        "Nuxt.js": ["NuxtJS"],
        "Redux": [],
        "Webpack": [],
        "Vite": [],
        "Tailwind CSS": ["TailwindCSS", "Tailwind"],
        "Bootstrap": [],
        "Material-UI": ["MUI"],
        "Ember.js": ["EmberJS"],
        "Backbone.js": [],
        "WebAssembly": ["WASM"],
    },
    "backend_frameworks": {
        "Spring Boot": ["Spring", "SpringBoot"],
        "Django": [],
        "Flask": [],
        "FastAPI": [],
        "Express.js": ["Express", "ExpressJS"],
        "NestJS": ["Nest.js"],
        "Ruby on Rails": ["Rails", "RoR"],
        "ASP.NET Core": ["ASP.NET", ".NET Core", "dotnet core"],
        ".NET Framework": ["dotnet framework", "DotNet"],
        "Laravel": [],
        "Symfony": [],
        "Node.js": ["NodeJS", "Node"],
    },
    "mobile_development": {
        "Android SDK": ["Android Development", "Android"],
        "iOS Development": ["iOS SDK", "iOS"],
        "React Native": [],
        "Flutter": [],
        "Xamarin": [],
        "Ionic": [],
        "SwiftUI": [],
        "Jetpack Compose": [],
    },
    "databases_relational": {
        "MySQL": [],
        "PostgreSQL": ["Postgres"],
        "Microsoft SQL Server": ["SQL Server", "MSSQL", "T-SQL"],
        "Oracle Database": ["Oracle DB", "OracleSQL", "PL/SQL"],
        "SQLite": [],
        "MariaDB": [],
        "IBM Db2": ["DB2"],
    },
    "databases_nosql": {
        "MongoDB": ["Mongo"],
        "Redis": [],
        "Cassandra": ["Apache Cassandra"],
        "Elasticsearch": ["ElasticSearch", "ES"],
        "DynamoDB": ["AWS DynamoDB"],
        "Couchbase": [],
        "Neo4j": [],
        "Firebase Firestore": ["Firestore"],
    },
    "cloud_platforms": {
        "Amazon Web Services": ["AWS"],
        "Microsoft Azure": ["Azure"],
        "Google Cloud Platform": ["GCP", "Google Cloud"],
        "IBM Cloud": [],
        "Oracle Cloud Infrastructure": ["OCI"],
        "Heroku": [],
        "DigitalOcean": [],
        "AWS Lambda": ["Lambda"],
        "Amazon EC2": ["EC2"],
        "Amazon S3": ["S3"],
        "Azure Functions": [],
        "Google Kubernetes Engine": ["GKE"],
    },
    "devops_ci_cd": {
        "Jenkins": [],
        "GitHub Actions": [],
        "GitLab CI/CD": ["GitLab CI"],
        "CircleCI": [],
        "Travis CI": [],
        "Azure DevOps": [],
        "ArgoCD": ["Argo CD"],
        "Bamboo": [],
        "TeamCity": [],
    },
    "containers_orchestration": {
        "Docker": [],
        "Kubernetes": ["K8s"],
        "Docker Compose": [],
        "Helm": [],
        "OpenShift": [],
        "Podman": [],
    },
    "infrastructure_as_code": {
        "Terraform": [],
        "Ansible": [],
        "Puppet": [],
        "Chef": [],
        "AWS CloudFormation": ["CloudFormation"],
        "Pulumi": [],
    },
    "version_control_collaboration": {
        "Git": [],
        "GitHub": [],
        "GitLab": [],
        "Bitbucket": [],
        "Subversion": ["SVN"],
        "Jira": [],
        "Confluence": [],
    },
    "testing_qa": {
        "JUnit": [],
        "pytest": ["PyTest"],
        "Selenium": [],
        "Cypress": [],
        "Jest": [],
        "Mocha": [],
        "TestNG": [],
        "Postman": [],
        "SoapUI": [],
        "Playwright": [],
        "Cucumber": [],
        "JMeter": ["Apache JMeter"],
    },
    "api_integration": {
        "REST API": ["RESTful API", "REST"],
        "GraphQL": [],
        "SOAP": [],
        "gRPC": [],
        "OpenAPI": ["Swagger"],
        "Webhooks": [],
    },
    "messaging_streaming": {
        "Apache Kafka": ["Kafka"],
        "RabbitMQ": [],
        "Amazon SQS": ["SQS"],
        "Amazon SNS": ["SNS"],
        "Apache Pulsar": [],
        "ActiveMQ": [],
    },
    "monitoring_observability": {
        "Prometheus": [],
        "Grafana": [],
        "Splunk": [],
        "Datadog": [],
        "New Relic": [],
        "ELK Stack": ["Elastic Stack"],
        "Logstash": [],
        "Kibana": [],
    },
    "operating_systems": {
        "Linux": [],
        "Ubuntu": [],
        "Red Hat Enterprise Linux": ["RHEL"],
        "CentOS": [],
        "Windows Server": [],
        "macOS": [],
        "Unix": [],
    },
    "web_servers_proxies": {
        "Nginx": [],
        "Apache HTTP Server": ["Apache", "httpd"],
        "IIS": ["Internet Information Services"],
        "HAProxy": [],
    },
    "build_tools_package_managers": {
        "Maven": [],
        "Gradle": [],
        "npm": [],
        "Yarn": [],
        "pnpm": [],
        "pip": [],
        "NuGet": [],
        "Make": [],
    },
    "data_engineering_bigdata": {
        "Apache Spark": ["Spark", "PySpark"],
        "Apache Hadoop": ["Hadoop"],
        "Apache Airflow": ["Airflow"],
        "dbt": [],
        "Snowflake": [],
        "Databricks": [],
        "Apache Hive": ["Hive"],
        "Apache Flink": [],
    },
    "machine_learning_ai": {
        "TensorFlow": [],
        "PyTorch": [],
        "scikit-learn": ["sklearn"],
        "Keras": [],
        "Pandas": [],
        "NumPy": [],
        "Hugging Face Transformers": ["Transformers", "HuggingFace"],
        "LangChain": [],
        "OpenAI API": [],
        "MLflow": [],
    },
    "security": {
        "OAuth 2.0": ["OAuth"],
        "OpenID Connect": ["OIDC"],
        "SSL/TLS": ["TLS", "SSL"],
        "OWASP": [],
        "Penetration Testing": ["Pen Testing"],
        "SIEM": [],
        "HashiCorp Vault": ["Vault"],
        "IAM": ["Identity and Access Management"],
    },
}

# category -> {canonical_name, lowered, for a canonical name or alias}, built once at import
# time so tools/agents can normalize a raw extracted string in O(1) without re-scanning
# COMMON_TECHNICAL_SKILLS on every lookup.
_ALIAS_INDEX: dict[str, tuple[str, str]] = {
    variant.lower(): (category, canonical)
    for category, skills in COMMON_TECHNICAL_SKILLS.items()
    for canonical, aliases in skills.items()
    for variant in (canonical, *aliases)
}


def normalize_technical_skill(raw: str) -> str | None:
    """Maps a raw skill string found in a resume/job posting to its canonical name.

    Lookup is case-insensitive against both canonical names and their known aliases.
    Returns None if `raw` isn't present in `COMMON_TECHNICAL_SKILLS`, leaving the
    caller free to keep the raw value or discard it.
    """
    match = _ALIAS_INDEX.get(raw.strip().lower())
    return match[1] if match else None


@mcp.resource(
    "resource://common-technical-skills",
    name="common_technical_skills",
    title="Common IT Technical Skills",
    description=(
        "Canonical taxonomy of IT technical skills (languages, frameworks, databases, "
        "cloud, DevOps, testing, data/ML, security, etc.) with their common aliases. "
        "Agents extracting skills from a resume or job posting use it to normalize what "
        "they find to one shared, unified vocabulary."
    ),
    mime_type="application/json",
)
def common_technical_skills() -> dict[str, dict[str, list[str]]]:
    """Returns the canonical IT technical-skill taxonomy."""
    return COMMON_TECHNICAL_SKILLS
