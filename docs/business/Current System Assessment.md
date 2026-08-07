# Current System Assessment

## Data Sources & Ingestion
Before asking how the data is stored, I'd first understand how it **gets there**.
### **Sources**
#### Where does the data originate?
#### What systems, organizations, people, instruments, or processes produce it?
#### What formats are produced?
#### Are sources structured, semi-structured, or unstructured?
#### Are there authoritative sources?

### **Ingestion**
#### How does data enter the platform?
#### Is ingestion automated or manual?
#### Batch, streaming, event-driven, or some combination?
#### How frequently is data ingested?
#### Is ingestion incremental or full-refresh?
#### What happens when ingestion fails?
#### Are duplicate records possible?
#### Can records arrive late or out of order?
#### How are schema changes handled?

### The deeper question
#### **How much human effort is required to reliably get data into the system?**
That often exposes enormous opportunities for improvement.

## Storage
This is the physical data layer.
### Questions
#### Where is the data physically stored?
#### What storage technologies are used?
#### Why were they chosen?
#### Is storage centralized or distributed?
#### How is data organized?
#### Is there a consistent directory/bucket/table structure?
#### Are there naming conventions?
#### What file formats are used?
#### Are files immutable or mutable?
#### How large are the files?
#### Are there many small files?
#### Is data partitioned?
#### What determines partitioning?
#### How is historical data managed?
#### How is data deleted?
#### How are backups performed?
#### How is data recovered?
#### How long is data retained?
#### Is storage growing faster than expected?

### The deeper question
#### Does the physical storage organization support the way the data is actually queried?
For example, your recent Iceberg work is directly relevant here. A technically valid collection of Parquet files isn't necessarily a well-designed storage system.
* * *

## Data Modeling
### Questions
#### What are the fundamental entities in the data?
#### How are those entities represented?
#### What are the relationships between them?
#### Are there defined schemas?
#### Are schemas enforced?
#### Are primary keys defined?
#### Are foreign-key relationships defined?
#### Are data types consistent?
#### Are domain concepts standardized?
#### Are there duplicated representations of the same concept?
#### Are historical changes represented appropriately?
#### Is the model normalized or denormalized?
#### Is there a distinction between raw, operational, analytical, and curated models?
### The deeper question
#### Does the data model represent the domain correctly?
You can have an extremely sophisticated data platform sitting underneath a fundamentally bad data model.
* * *

## Metadata
Your instinct here is exactly right.
But metadata is broader than just "schema."
### Technical metadata
#### Schema
#### Data types
#### File formats
#### Table locations
#### Partition information
#### Statistics
#### File sizes
#### Modification times
### Business/domain metadata
#### What does this dataset mean?
#### What does each field mean?
#### What units are used?
#### What are valid values?
#### What assumptions were made?
#### Who is responsible for it?
### Operational metadata
#### When was data last updated?
#### When did a pipeline last run?
#### How long did it take?
#### Did it succeed?
#### How many records were processed?
### Core Questions
#### Where is metadata stored?
#### Is metadata centralized?
#### Is metadata automatically generated?
#### Is it manually maintained?
#### Is it versioned?
#### Is it stale?
#### Can users search it?
#### Is metadata associated with the data it describes?
This leads directly into discoverability.
* * *

## Compute & Analytics
This is the layer you've been learning through Spark.
### Questions
#### What technologies perform computation?
#### Where does computation occur?
#### SQL? Python? Spark? dbt? custom applications?
#### Is computation centralized or performed locally by users?
#### Where do transformations occur?
#### Are transformations reproducible?
#### Are transformations version controlled?
#### Are jobs scheduled?
#### Are jobs dependent on one another?
#### How are failures handled?
#### Can processing scale?
#### Are compute resources efficiently utilized?
#### Is data repeatedly recomputed unnecessarily?
### The deeper question
#### Where does business logic live?
This is a huge one.
For example, if ten analysts each have slightly different Python scripts implementing "annual precipitation," you've got a data-platform problem even if the underlying data is pristine.
* * *

## Data Quality
I'd divide this into **dimensions of quality** and **mechanisms for measuring quality**.
### Dimensions
#### Accuracy
#### Completeness
#### Consistency
#### Timeliness
#### Uniqueness
#### Validity
#### Integrity
#### Conformity
### Questions
#### What constitutes "good" data?
#### Are quality rules explicitly defined?
#### Where are quality checks performed?
#### Are checks automated?
#### Are they performed during ingestion or afterward?
#### What happens when a check fails?
#### Is bad data rejected, quarantined, corrected, or allowed through?
#### Are quality metrics tracked over time?
#### Can users see quality information?
#### Is quality assessed at the dataset, record, or field level?
### The deeper question
#### Is data quality enforced, or merely observed?
There's a big difference.
* * *

## Validation & Auditability
I would separate this from general quality.
Quality asks:
> "Is this data good?"  
> Auditability asks:  
>   
> **"Can we demonstrate why we believe this data is good?"**
### Questions
#### Can we reproduce how a dataset was generated?
#### Can we determine when it was generated?
#### Who generated or modified it?
#### What source data was used?
#### What transformations occurred?
#### What validation was performed?
#### What version of the code performed the transformation?
#### What version of the source data was used?
#### Are validation results retained?
#### Can historical states be reconstructed?
#### Can changes be detected?
This is where technologies such as **Iceberg snapshots, versioning, lineage systems, checksums, validation reports, and immutable raw data** become relevant.
* * *

## Lineage & Traceability
This deserves its own category in my opinion.
### The deeper question:
> **Can I trace this piece of data backward to its origin and forward to everything that depends on it?**  
> For example:

```css
Source instrument
      ↓
Raw file
      ↓
Bronze table
      ↓
Silver transformation
      ↓
Gold dataset
      ↓
Model input
      ↓
Hydrologic simulation
      ↓
Report



```

### Questions
#### Where did this data originate?
#### What transformations occurred?
#### What datasets contributed to it?
#### What downstream products depend on it?
#### Can lineage be automatically captured?
#### Is lineage historical/versioned?
#### Can a user inspect lineage?
This becomes **extremely important** in scientific, regulatory, financial, and engineering environments.
* * *

## Accessibility & Data Serving
Your category here is also excellent.
### First Questions
#### Who consumes the data?
#### What interfaces are available?
#### SQL?
#### APIs?
#### Files?
#### Object storage?
#### Dashboards?
#### Python libraries?
#### GIS services?
#### Direct database connections?
### Followup Questions
#### Is access self-service?
#### Do users need engineering assistance?
#### Is the data standardized?
#### Are schemas stable?
#### Are APIs versioned?
#### Are access patterns documented?
#### Can users query the data efficiently?
#### Are extracts required?
#### Are users downloading entire datasets because targeted querying isn't possible?
### The deeper question
#### What does a typical user have to do to obtain the data they need?
If the answer is:
> "Ask Bob, who runs a script, exports a CSV, puts it on SharePoint, and emails you the link..."  
> you've found a platform opportunity.
* * *

## Discoverability
This is closely related to metadata but deserves independent attention.
### Questions
#### How does someone know what datasets exist?
#### Is there a catalog?
#### Can users search datasets?
#### Can they search fields?
#### Can they search by domain concepts?
#### Can they filter by spatial/temporal coverage?
#### Can they see ownership?
#### Can they see freshness?
#### Can they see quality?
#### Can they see lineage?
#### Can they see examples?
#### Can they determine whether two datasets contain overlapping information?
### The deeper question
#### Can a new user independently find and understand the correct dataset without asking another person?
That's a very strong measure of platform maturity.
* * *

## Governance & Security
This is one I'd add to your framework.
### Ownership Questions
#### Who owns each dataset?
#### Who is responsible for maintaining it?
#### Who determines its meaning?
#### Who approves changes?
### Access Control Questions
#### Who can read it?
#### Who can modify it?
#### Who can delete it?
#### Is access role-based?
#### Is access centrally managed?
### Governance Questions
#### Are naming conventions defined?
#### Are schemas governed?
#### Are standards documented?
#### Are retention policies defined?
#### Are sensitive datasets identified?
### Compliance Questions
#### Are there regulatory requirements?
#### Are there contractual restrictions?
#### Are there data residency requirements?
#### Are there audit requirements?
* * *

## Reliability & Operations
This is another major layer missing from your original framework.
A data platform isn't just a collection of technologies. It's an **operated system**.
### Questions
#### How do you know when something breaks?
#### Is there monitoring?
#### Are pipelines observable?
#### Are failures logged?
#### Are alerts generated?
#### Are SLAs/SLOs defined?
#### How are incidents handled?
#### How are failed jobs retried?
#### How are corrupted datasets recovered?
#### How are schema changes detected?
#### How are dependencies managed?
#### Are operational metrics collected?
For example:

```markdown
Pipeline failed
      ↓
Was it detected?
      ↓
Was someone notified?
      ↓
Can they determine why?
      ↓
Can they fix it?
      ↓
Can they safely rerun it?
      ↓
Can they verify the result?



```

That sequence tells you a **lot** about the maturity of a data platform.
* * *

## Performance & Scalability
Finally, I'd ask whether the architecture will continue working as the system grows.
### Data Growth Questions
#### How much data exists today?
#### How fast is it growing?
#### What is the expected growth rate?
#### What is the largest dataset?
### Query Growth Questions
#### How many users?
#### How many queries?
#### What are typical query sizes?
#### What are the slowest queries?
#### What are the most expensive operations?
### System Growth Questions
#### What happens if data volume increases 10×?
#### What happens if users increase 10×?
#### What happens if ingestion frequency increases 10×?
### The deeper question
#### What is the current bottleneck?
> **Storage? Network? Compute? Database connections? Metadata? Human labor?**

## Important cross-cutting questions
### Storage ↔ Compute
#### Does the storage architecture support the compute/query patterns?
### Metadata ↔ Discoverability
#### Is the metadata sufficient for users to find and understand data?
### Quality ↔ Accessibility
#### Do consumers know whether the data they're accessing is trustworthy?
### Lineage ↔ Auditability
#### Can we reconstruct how a dataset was produced?
### Governance ↔ Accessibility
#### Can people access the data they need without exposing data they shouldn't?
### Ingestion ↔ Quality
#### Are quality problems detected before they propagate downstream?
### Modeling ↔ Analytics
#### Does the data model make common analytical tasks easy or difficult?
### Operations ↔ Everything
#### Can we detect, diagnose, recover from, and prevent failures?