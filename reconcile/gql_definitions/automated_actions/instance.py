"""
Generated by qenerate plugin=pydantic_v1. DO NOT MODIFY MANUALLY!
"""
from collections.abc import Callable  # noqa: F401 # pylint: disable=W0611
from datetime import datetime  # noqa: F401 # pylint: disable=W0611
from enum import Enum  # noqa: F401 # pylint: disable=W0611
from typing import (  # noqa: F401 # pylint: disable=W0611
    Any,
    Optional,
    Union,
)

from pydantic import (  # noqa: F401 # pylint: disable=W0611
    BaseModel,
    Extra,
    Field,
    Json,
)

from reconcile.gql_definitions.fragments.oc_connection_cluster import OcConnectionCluster


DEFINITION = """
fragment CommonJumphostFields on ClusterJumpHost_v1 {
  hostname
  knownHosts
  user
  port
  remotePort
  identity {
    ... VaultSecret
  }
}

fragment OcConnectionCluster on Cluster_v1 {
  name
  serverUrl
  internal
  insecureSkipTLSVerify
  jumpHost {
    ...CommonJumphostFields
  }
  automationToken {
    ...VaultSecret
  }
  clusterAdminAutomationToken {
    ...VaultSecret
  }
  disable {
    integrations
  }
}

fragment VaultSecret on VaultSecret_v1 {
    path
    field
    version
    format
}

query AutomatedActionsInstances {
  automated_actions_instances_v1 {
    name
    deployment {
      name
      clusterAdmin
      delete
      cluster {
        ...OcConnectionCluster
      }
    }
    permissions {
      roles {
        name
        users {
          org_username
        }
        bots {
          org_username
        }
        expirationDate
      }

      action {
        operationId
        retries
        maxOps
      }

      arguments {
        type
        ... on AutomatedActionArgumentOpenshift_v1 {
          namespace {
            name
            delete
            cluster {
              name
              disable {
                integrations
              }
            }
          }
          kind_pattern
          name_pattern
        }
      }
    }
  }
}
"""


class ConfiguredBaseModel(BaseModel):
    class Config:
        smart_union=True
        extra=Extra.forbid


class NamespaceV1(ConfiguredBaseModel):
    name: str = Field(..., alias="name")
    cluster_admin: Optional[bool] = Field(..., alias="clusterAdmin")
    delete: Optional[bool] = Field(..., alias="delete")
    cluster: OcConnectionCluster = Field(..., alias="cluster")


class UserV1(ConfiguredBaseModel):
    org_username: str = Field(..., alias="org_username")


class BotV1(ConfiguredBaseModel):
    org_username: Optional[str] = Field(..., alias="org_username")


class RoleV1(ConfiguredBaseModel):
    name: str = Field(..., alias="name")
    users: list[UserV1] = Field(..., alias="users")
    bots: list[BotV1] = Field(..., alias="bots")
    expiration_date: Optional[str] = Field(..., alias="expirationDate")


class AutomatedActionV1(ConfiguredBaseModel):
    operation_id: str = Field(..., alias="operationId")
    retries: int = Field(..., alias="retries")
    max_ops: int = Field(..., alias="maxOps")


class AutomatedActionArgumentV1(ConfiguredBaseModel):
    q_type: str = Field(..., alias="type")


class DisableClusterAutomationsV1(ConfiguredBaseModel):
    integrations: Optional[list[str]] = Field(..., alias="integrations")


class AutomatedActionArgumentOpenshiftV1_NamespaceV1_ClusterV1(ConfiguredBaseModel):
    name: str = Field(..., alias="name")
    disable: Optional[DisableClusterAutomationsV1] = Field(..., alias="disable")


class AutomatedActionArgumentOpenshiftV1_NamespaceV1(ConfiguredBaseModel):
    name: str = Field(..., alias="name")
    delete: Optional[bool] = Field(..., alias="delete")
    cluster: AutomatedActionArgumentOpenshiftV1_NamespaceV1_ClusterV1 = Field(..., alias="cluster")


class AutomatedActionArgumentOpenshiftV1(AutomatedActionArgumentV1):
    namespace: AutomatedActionArgumentOpenshiftV1_NamespaceV1 = Field(..., alias="namespace")
    kind_pattern: str = Field(..., alias="kind_pattern")
    name_pattern: str = Field(..., alias="name_pattern")


class PermissionAutomatedActionsV1(ConfiguredBaseModel):
    roles: Optional[list[RoleV1]] = Field(..., alias="roles")
    action: AutomatedActionV1 = Field(..., alias="action")
    arguments: Optional[list[Union[AutomatedActionArgumentOpenshiftV1, AutomatedActionArgumentV1]]] = Field(..., alias="arguments")


class AutomatedActionsInstanceV1(ConfiguredBaseModel):
    name: str = Field(..., alias="name")
    deployment: NamespaceV1 = Field(..., alias="deployment")
    permissions: Optional[list[PermissionAutomatedActionsV1]] = Field(..., alias="permissions")


class AutomatedActionsInstancesQueryData(ConfiguredBaseModel):
    automated_actions_instances_v1: Optional[list[AutomatedActionsInstanceV1]] = Field(..., alias="automated_actions_instances_v1")


def query(query_func: Callable, **kwargs: Any) -> AutomatedActionsInstancesQueryData:
    """
    This is a convenience function which queries and parses the data into
    concrete types. It should be compatible with most GQL clients.
    You do not have to use it to consume the generated data classes.
    Alternatively, you can also mime and alternate the behavior
    of this function in the caller.

    Parameters:
        query_func (Callable): Function which queries your GQL Server
        kwargs: optional arguments that will be passed to the query function

    Returns:
        AutomatedActionsInstancesQueryData: queried data parsed into generated classes
    """
    raw_data: dict[Any, Any] = query_func(DEFINITION, **kwargs)
    return AutomatedActionsInstancesQueryData(**raw_data)
