/* Service directory — a curated map of real Azure Retail Prices `serviceName` values grouped by
   `serviceFamily`. This is navigation metadata only (no prices); choosing a service fires a single
   narrow /api/pricing query for the picked region, instead of snapshotting a whole region at once.
   That keeps us well inside the Azure Retail Prices API's request budget.

   Names mirror the API's own `serviceName` strings. If a service has no meter in a given region the
   results view says so honestly — nothing here is invented. */
(function () {
  "use strict";

  // family -> services. Ordered by how often people price each family.
  var FAMILIES = [
    {
      family: "Compute",
      blurb: "Virtual machines, app hosting, and serverless",
      services: [
        "Virtual Machines",
        "Azure App Service",
        "Functions",
        "Azure Kubernetes Service",
        "Container Instances",
        "Azure Container Apps",
        "Container Registry",
        "Batch",
        "Azure VMware Solution",
      ],
    },
    {
      family: "Databases",
      blurb: "Managed SQL, open-source, and NoSQL",
      services: [
        "SQL Database",
        "SQL Managed Instance",
        "Azure Database for MySQL",
        "Azure Database for PostgreSQL",
        "Azure Database for MariaDB",
        "Azure Cosmos DB",
        "Redis Cache",
      ],
    },
    {
      family: "Storage",
      blurb: "Blobs, files, and data protection",
      services: ["Storage", "Azure Files", "Azure NetApp Files", "Backup", "Azure Data Lake Storage Gen2"],
    },
    {
      family: "Networking",
      blurb: "Connectivity, delivery, and edge security",
      services: [
        "Virtual Network",
        "Load Balancer",
        "Application Gateway",
        "VPN Gateway",
        "Azure Firewall",
        "Azure Front Door Service",
        "Content Delivery Network",
        "Azure Bastion",
        "NAT Gateway",
        "Bandwidth",
      ],
    },
    {
      family: "Analytics",
      blurb: "Streaming, big data, and pipelines",
      services: [
        "Azure Synapse Analytics",
        "Azure Databricks",
        "HDInsight",
        "Event Hubs",
        "Azure Data Factory v2",
        "Azure Data Explorer",
      ],
    },
    {
      family: "AI + Machine Learning",
      blurb: "Cognitive APIs and model training",
      services: ["Azure Machine Learning", "Cognitive Services", "Azure Bot Service"],
    },
    {
      family: "Integration",
      blurb: "Messaging, events, and APIs",
      services: ["Service Bus", "Event Grid", "Logic Apps", "API Management"],
    },
    {
      family: "Security + Management",
      blurb: "Secrets, monitoring, and recovery",
      services: ["Key Vault", "Azure Monitor", "Log Analytics", "Azure Site Recovery"],
    },
  ];

  // SKU-priced services worth flagging — these reward the per-SKU results table.
  var PER_SKU = { "Virtual Machines": true, "Azure App Service": true, "SQL Database": true };

  function all() {
    var flat = [];
    FAMILIES.forEach(function (group) {
      group.services.forEach(function (name) {
        flat.push({ serviceName: name, serviceFamily: group.family, perSku: !!PER_SKU[name] });
      });
    });
    return flat;
  }

  window.ServiceCatalog = {
    families: FAMILIES,
    all: all,
    perSku: PER_SKU,
  };
})();
