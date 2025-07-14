# Managing tenants

`sqlalchemy-tenants` focus is on enforcing data isolation among tenants. As such, 
it assumes you already have a system for managing and controlling your tenants and 
respective settings. 

You'll likely already have a table or service that tracks tenant information and configuration.
`sqlalchemy-tenants` expects you to use the identifier you're using for tenants (e.g. a slug or ID)
in the tables that need to be tenant-aware. This identifier will be used to 
create database roles and policies for each tenant.


## Creating tenants

You can manually create a tenant using [PostgresManager.create_tenant()][sqlalchemy_tenants.managers.PostgresManager.create_tenant]


