# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

import os
import time
import unittest

from azure.cli.testsdk import (ScenarioTest, LiveScenarioTest, ResourceGroupPreparer,
                               JMESPathCheck as JCheck, create_random_name)
# AZURE CLI RESOURCE TEST DEFINITIONS
from azure.cli.testsdk import TestCli
from azure.cli.testsdk.vcr_test_base import (VCRTestBase, JMESPathCheck, NoneCheck,
                                             BooleanCheck,
                                             ResourceGroupVCRTestBase,
                                             MOCKED_SUBSCRIPTION_ID)


class ResourceGroupScenarioTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_rg_scenario')
    def test_resource_group(self, resource_group):
        s = self
        rg = resource_group
        s.cmd('group delete -n {} --yes'.format(rg))
        s.cmd('group exists -n {}'.format(rg), checks=NoneCheck())

        s.cmd('group create -n {} -l westus --tag a=b c'.format(rg), checks=[
            JCheck('name', rg),
            JCheck('tags', {'a': 'b', 'c': ''})
        ])
        s.cmd('group exists -n {}'.format(rg), checks=BooleanCheck(True))
        s.cmd('group show -n {}'.format(rg), checks=[
            JCheck('name', rg),
            JCheck('tags', {'a': 'b', 'c': ''})
        ])
        s.cmd('group list --tag a=b', checks=[
            JCheck('[0].name', rg),
            JCheck('[0].tags', {'a': 'b', 'c': ''})
        ])


class ResourceGroupNoWaitScenarioTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_rg_nowait_test')
    def test_resource_group_no_wait(self, resource_group):
        s = self
        rg = resource_group
        s.cmd('group delete -n {} --no-wait --yes'.format(rg), checks=NoneCheck())
        s.cmd('group wait --deleted -n {}'.format(rg), checks=NoneCheck())
        s.cmd('group exists -n {}'.format(rg), checks=NoneCheck())
        s.cmd('group create -n {} -l westus'.format(rg), checks=JCheck('name', rg))
        s.cmd('group exists -n {}'.format(rg), checks=BooleanCheck(True))
        s.cmd('group wait --exists -n {}'.format(rg), checks=NoneCheck())


class ResourceScenarioTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_resource_scenario')
    def test_resource_scenario(self, resource_group):
        s = self
        rg = resource_group
        vnet_name = 'cli-test-vnet1'
        subnet_name = 'cli-test-subnet1'
        vnet_count = s.cmd("resource list --query \"length([?name=='{}'])\"".format(vnet_name)).get_output_in_json() or 0
        s.cmd('network vnet create -g {} -n {} --subnet-name {} --tags cli-test=test'.format(rg, vnet_name, subnet_name))
        vnet_count += 1

        s.cmd('resource list',
              checks=JCheck("length([?name=='{}'])".format(vnet_name), vnet_count))
        s.cmd('resource list -l centralus',
              checks=JCheck("length([?location == 'centralus']) == length(@)", True))
        s.cmd('resource list --resource-type Microsoft.Network/virtualNetworks',
              checks=JCheck("length([?name=='{}'])".format(vnet_name), vnet_count))
        s.cmd('resource list --name {}'.format(vnet_name),
              checks=JCheck("length([?name=='{}'])".format(vnet_name), vnet_count))
        s.cmd('resource list --tag cli-test',
              checks=JCheck("length([?name=='{}'])".format(vnet_name), vnet_count))
        s.cmd('resource list --tag cli-test=test',
              checks=JCheck("length([?name=='{}'])".format(vnet_name), vnet_count))

        # check for simple resource with tag
        s.cmd('resource show -n {} -g {} --resource-type Microsoft.Network/virtualNetworks'.format(
            vnet_name, rg), checks=[
            JCheck('name', vnet_name),
            JCheck('location', 'westus'),
            JCheck('resourceGroup', rg),
            JCheck('tags', {'cli-test': 'test'})
        ])
        # check for child resource
        s.cmd('resource show -n {} -g {} --namespace Microsoft.Network --parent virtualNetworks/{} --resource-type subnets'.format(subnet_name, rg, vnet_name), checks=[
            JCheck('name', subnet_name),
            JCheck('resourceGroup', rg),
        ])

        # clear tag and verify
        s.cmd('resource tag -n {} -g {} --resource-type Microsoft.Network/virtualNetworks --tags'.format(vnet_name, rg))
        s.cmd('resource show -n {} -g {} --resource-type Microsoft.Network/virtualNetworks'.format(vnet_name, rg),
            checks=JCheck('tags', {}))


class ResourceIDScenarioTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_resource_id')
    def test_resource_id_scenario(self, resource_group):
        vnet_name = 'cli_test_resource_id_vnet'
        subnet_name = 'cli_test_resource_id_subnet'

        self.cmd('network vnet create -g {} -n {} --subnet-name {}'.format(resource_group, vnet_name, subnet_name))

        if self.in_recording:
            from azure.cli.core.commands.client_factory import get_subscription_id
            subscription_id = get_subscription_id(self.ctx)
        else:
            subscription_id = MOCKED_SUBSCRIPTION_ID

        s = self
        vnet_resource_id = '/subscriptions/{}/resourceGroups/{}/providers/Microsoft.Network/virtualNetworks/{}'.format(
            subscription_id, resource_group, vnet_name)
        s.cmd('resource tag --id {} --tags {}'.format(vnet_resource_id, 'tag-vnet'))
        s.cmd('resource show --id {}'.format(vnet_resource_id), checks=[
            JCheck('name', vnet_name),
            JCheck('resourceGroup', resource_group),
            JCheck('tags', {'tag-vnet': ''})
        ])

        subnet_resource_id = '/subscriptions/{}/resourceGroups/{}/providers/Microsoft.Network/virtualNetworks/{}/subnets/{}'.format(
            subscription_id, resource_group, vnet_name, subnet_name)
        s.cmd('resource show --id {}'.format(subnet_resource_id), checks=[
            JCheck('name', subnet_name),
            JCheck('resourceGroup', resource_group),
            JCheck('properties.addressPrefix', '10.0.0.0/24')
        ])

        s.cmd('resource update --id {} --set properties.addressPrefix=10.0.0.0/22'.format(subnet_resource_id),
            checks=JCheck('properties.addressPrefix', '10.0.0.0/22'))

        s.cmd('resource delete --id {}'.format(subnet_resource_id), checks=NoneCheck())
        s.cmd('resource delete --id {}'.format(vnet_resource_id), checks=NoneCheck())


class ResourceCreateScenarioTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_resource_create')
    def test_resource_create(self, resource_group, resource_group_location):
        appservice_plan = 'cli_res_create_plan'
        webapp = 'clirescreateweb'

        self.cmd('resource create -g {} -n {} --resource-type Microsoft.web/serverFarms --is-full-object --properties "{{\\"location\\":\\"{}\\",\\"sku\\":{{\\"name\\":\\"B1\\",\\"tier\\":\\"BASIC\\"}}}}"'.format(resource_group, appservice_plan, resource_group_location),
                 checks=JCheck('name', appservice_plan))

        result = self.cmd('resource create -g {} -n {} --resource-type Microsoft.web/sites --properties "{{\\"serverFarmId\\":\\"{}\\"}}"'.format(resource_group, webapp, appservice_plan),
                          checks=JCheck('name', webapp)).get_output_in_json()

        app_settings_id = result['id'] + '/config/appsettings'
        self.cmd('resource create --id {} --properties "{{\\"key2\\":\\"value12\\"}}"'.format(
            app_settings_id), checks=[JCheck('properties.key2', 'value12')])


class TagScenarioTest(ScenarioTest):

    def test_tag_scenario(self):
        s = self
        tn = 'cli_test_tag'
        tags = self.cmd('tag list --query "[?tagName == \'{}\'].values[].tagValue"'.format(tn)).get_output_in_json()
        for tag in tags:
            self.cmd('tag remove-value -n {} --value {}'.format(tn, tag))
        self.cmd('tag delete -n {}'.format(tn))

        s.cmd('tag list --query "[?tagName == \'{}\']"'.format(tn),
              checks=NoneCheck())
        s.cmd('tag create -n {}'.format(tn), checks=[
            JCheck('tagName', tn),
            JCheck('values', []),
            JCheck('count.value', 0)
        ])
        s.cmd('tag add-value -n {} --value test'.format(tn))
        s.cmd('tag add-value -n {} --value test2'.format(tn))
        s.cmd('tag list --query "[?tagName == \'{}\']"'.format(tn),
              checks=JCheck('[].values[].tagValue', [u'test', u'test2']))
        s.cmd('tag remove-value -n {} --value test'.format(tn))
        s.cmd('tag list --query "[?tagName == \'{}\']"'.format(tn),
              checks=JCheck('[].values[].tagValue', [u'test2']))
        s.cmd('tag remove-value -n {} --value test2'.format(tn))
        s.cmd('tag list --query "[?tagName == \'{}\']"'.format(tn),
              checks=JCheck('[].values[].tagValue', []))
        s.cmd('tag delete -n {}'.format(tn))
        s.cmd('tag list --query "[?tagName == \'{}\']"'.format(tn),
              checks=NoneCheck())


class ProviderRegistrationTest(ScenarioTest):

    def test_provider_registration(self):
        provider = 'TrendMicro.DeepSecurity'
        result = self.cmd('provider show -n {}'.format(provider), checks=None).get_output_in_json()
        if result['registrationState'] == 'Unregistered':
            self.cmd('provider register -n {}'.format(provider), checks=None)
            result = self.cmd('provider show -n {}'.format(provider)).get_output_in_json()
            self.assertTrue(result['registrationState'] in ['Registering', 'Registered'])
            self.cmd('provider unregister -n {}'.format(provider), checks=None)
            result = self.cmd('provider show -n {}'.format(provider)).get_output_in_json()
            self.assertTrue(result['registrationState'] in ['Unregistering', 'Unregistered'])
        else:
            self.cmd('provider unregister -n {}'.format(provider), checks=None)
            result = self.cmd('provider show -n {}'.format(provider)).get_output_in_json()
            self.assertTrue(result['registrationState'] in ['Unregistering', 'Unregistered'])
            self.cmd('provider register -n {}'.format(provider), checks=None)
            result = self.cmd('provider show -n {}'.format(provider)).get_output_in_json()
            self.assertTrue(result['registrationState'] in ['Registering', 'Registered'])


class ProviderOperationTest(ScenarioTest):

    def test_provider_operation(self):
        self.cmd('provider operation show --namespace microsoft.compute', checks=[
            JCheck('id', '/providers/Microsoft.Authorization/providerOperations/Microsoft.Compute'),
            JCheck('type', 'Microsoft.Authorization/providerOperations')
        ])
        self.cmd('provider operation show --namespace microsoft.compute --api-version 2015-07-01', checks=[
            JCheck('id', '/providers/Microsoft.Authorization/providerOperations/Microsoft.Compute'),
            JCheck('type', 'Microsoft.Authorization/providerOperations')
        ])


class DeploymentTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_deployment')
    def test_group_deployment(self, resource_group):
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        template_file = os.path.join(curr_dir, 'test-template.json').replace('\\', '\\\\')
        parameters_file = os.path.join(curr_dir, 'test-params.json').replace('\\', '\\\\')
        object_file = os.path.join(curr_dir, 'test-object.json').replace('\\', '\\\\')
        deployment_name = 'azure-cli-deployment'

        subnet_id = self.cmd('network vnet create -g {} -n vnet1 --subnet-name subnet1'.format(resource_group)).get_output_in_json()['subnets'][0]['id']

        self.cmd('group deployment validate -g {} --template-file {} --parameters @"{}" --parameters subnetId="{}" --parameters backendAddressPools=@"{}"'.format(
            resource_group, template_file, parameters_file, subnet_id, object_file), checks=[
            JCheck('properties.provisioningState', 'Succeeded')
        ])

        self.cmd('group deployment create -g {} -n {} --template-file {} --parameters @"{}" --parameters subnetId="{}" --parameters backendAddressPools=@"{}"'.format(
            resource_group, deployment_name, template_file, parameters_file, subnet_id, object_file), checks=[
            JCheck('properties.provisioningState', 'Succeeded'),
            JCheck('resourceGroup', resource_group),
        ])
        self.cmd('network lb show -g {} -n test-lb'.format(resource_group), checks=[
            JCheck('tags', {'key': 'super=value'})
        ])

        self.cmd('group deployment list -g {}'.format(resource_group), checks=[
            JCheck('[0].name', deployment_name),
            JCheck('[0].resourceGroup', resource_group)
        ])
        self.cmd('group deployment show -g {} -n {}'.format(resource_group, deployment_name), checks=[
            JCheck('name', deployment_name),
            JCheck('resourceGroup', resource_group)
        ])
        self.cmd('group deployment operation list -g {} -n {}'.format(resource_group, deployment_name), checks=[
            JCheck('length([])', 2),
            JCheck('[0].resourceGroup', resource_group)
        ])


class DeploymentLiveTest(LiveScenarioTest):
    @ResourceGroupPreparer()
    def test_group_deployment_progress(self, resource_group):
        from azure.cli.testsdk.utilities import force_progress_logging
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        template_file = os.path.join(curr_dir, 'test-template.json').replace('\\', '\\\\')
        parameters_file = os.path.join(curr_dir, 'test-params.json').replace('\\', '\\\\')
        object_file = os.path.join(curr_dir, 'test-object.json').replace('\\', '\\\\')
        deployment_name = 'azure-cli-deployment2'

        subnet_id = self.cmd('network vnet create -g {} -n vnet1 --subnet-name subnet1'.format(resource_group)).get_output_in_json()['subnets'][0]['id']

        with force_progress_logging() as test_io:
            self.cmd('group deployment create --verbose -g {} -n {} --template-file {} --parameters @"{}" --parameters subnetId="{}" --parameters backendAddressPools=@"{}"'.format(
                resource_group, deployment_name, template_file, parameters_file, subnet_id, object_file))

        # very the progress
        lines = test_io.getvalue().splitlines()
        for l in lines:
            self.assertTrue(l.split(':')[0] in ['Accepted', 'Succeeded'])
        self.assertTrue('Succeeded: {} (Microsoft.Resources/deployments)'.format(deployment_name), lines)


class DeploymentnoWaitTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_group_deployment_no_wait')
    def test_group_deployment_no_wait(self, resource_group):
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        template_file = os.path.join(curr_dir, 'simple_deploy.json').replace('\\', '\\\\')
        parameters_file = os.path.join(curr_dir, 'simple_deploy_parameters.json').replace('\\', '\\\\')
        deployment_name = 'azure-cli-deployment'

        self.cmd('group deployment create -g {} -n {} --template-file {} --parameters @{} --no-wait'.format(resource_group, deployment_name, template_file, parameters_file),
                 checks=NoneCheck())

        self.cmd('group deployment wait -g {} -n {} --created'.format(resource_group, deployment_name),
                 checks=NoneCheck())

        self.cmd('group deployment show -g {} -n {}'.format(resource_group, deployment_name),
                 checks=JMESPathCheck('properties.provisioningState', 'Succeeded'))


class DeploymentThruUriTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_deployment_uri')
    def test_group_deployment_thru_uri(self, resource_group):
        self.resource_group = resource_group
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        # same copy of the sample template file under current folder, but it is uri based now
        template_uri = 'https://raw.githubusercontent.com/Azure/azure-cli/master/src/' \
                       'command_modules/azure-cli-resource/azure/cli/command_modules/resource/tests/simple_deploy.json'
        parameters_file = os.path.join(curr_dir, 'simple_deploy_parameters.json').replace('\\',
                                                                                          '\\\\')
        result = self.cmd('group deployment create -g {} --template-uri {} --parameters @{}'.format(
            self.resource_group, template_uri, parameters_file), checks=[
            JCheck('properties.provisioningState', 'Succeeded'),
            JCheck('resourceGroup', self.resource_group),
        ]).get_output_in_json()

        deployment_name = result['name']
        result = self.cmd(
            'group deployment show -g {} -n {}'.format(self.resource_group, deployment_name), checks=JCheck('name', deployment_name))

        self.cmd('group deployment delete -g {} -n {}'.format(self.resource_group, deployment_name))
        self.cmd('group deployment list -g {}'.format(self.resource_group), checks=NoneCheck())


class ResourceMoveScenarioTest(ScenarioTest):


    @ResourceGroupPreparer(name_prefix='cli_test_res_move_src', parameter_name='src_resource_group')
    @ResourceGroupPreparer(name_prefix='cli_test_res_move_dst', parameter_name='dst_resource_group')
    def test_resource_move(self, src_resource_group, dst_resource_group):
        if self.in_recording:
            subscription_id = self.cmd('account list --query "[?isDefault].id"').get_output_in_json()[0]
        else:
            subscription_id = MOCKED_SUBSCRIPTION_ID

        # use 'network security group' for testing as it is fast to create
        nsg1 = 'nsg1'
        nsg1_id = '/subscriptions/{}/resourceGroups/{}/providers/Microsoft.Network/networkSecurityGroups/{}'.format(subscription_id, src_resource_group, nsg1)
        nsg2 = 'nsg2'
        nsg2_id = nsg1_id.replace(nsg1, nsg2)

        self.cmd('network nsg create -g {} --name {}'.format(src_resource_group, nsg1))
        self.cmd('network nsg create -g {} --name {}'.format(src_resource_group, nsg2))

        # move
        self.cmd('resource move --ids {} {} --destination-group {}'.format(nsg1_id, nsg2_id, dst_resource_group))

        # see they show up at destination
        self.cmd('network nsg show -g {} -n {}'.format(dst_resource_group, nsg1), checks=JCheck('name', nsg1))
        self.cmd('network nsg show -g {} -n {}'.format(dst_resource_group, nsg2), checks=JCheck('name', nsg2))


class FeatureScenarioTest(ScenarioTest):

    def test_feature_list(self):
        self.cmd('feature list', checks=JCheck("length([?name=='Microsoft.Xrm/uxdevelopment'])", 1))

        self.cmd('feature list --namespace {}'.format('Microsoft.Network'),
                 checks=JCheck("length([?name=='Microsoft.Network/SkipPseudoVipGeneration'])", 1))


class PolicyScenarioTest(ScenarioTest):
    @ResourceGroupPreparer(name_prefix='cli_test_policy')
    def test_resource_policy(self, resource_group):
        policy_name = 'azure-cli-test-policy'
        policy_display_name = 'test_policy_123'
        policy_description = 'test_policy_123'
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        rules_file = os.path.join(curr_dir, 'sample_policy_rule.json').replace('\\', '\\\\')

        # create a policy
        self.cmd('policy definition create -n {} --rules {} --display-name {} --description {}'.format(policy_name, rules_file, policy_display_name, policy_description), checks=[
            JCheck('name', policy_name),
            JCheck('displayName', policy_display_name),
            JCheck('description', policy_description)
        ])

        # update it
        new_policy_description = policy_description + '_new'
        self.cmd('policy definition update -n {} --description {}'.format(policy_name, new_policy_description),
                 checks=JCheck('description', new_policy_description))

        # list and show it
        self.cmd('policy definition list', checks=JMESPathCheck("length([?name=='{}'])".format(policy_name), 1))
        self.cmd('policy definition show -n {}'.format(policy_name), checks=[
            JCheck('name', policy_name),
            JCheck('displayName', policy_display_name)
        ])

        # create a policy assignment on a resource group
        policy_assignment_name = 'azurecli-test-policy-assignment'
        policy_assignment_display_name = 'test_assignment_123'
        self.cmd('policy assignment create --policy {} -n {} --display-name {} -g {}'.format(policy_name, policy_assignment_name, policy_assignment_display_name, resource_group), checks=[
            JCheck('name', policy_assignment_name),
            JCheck('displayName', policy_assignment_display_name),
        ])

        # listing at subscription level won't find the assignment made at a resource group
        import jmespath
        try:
            self.cmd('policy assignment list', checks=JCheck("length([?name=='{}'])".format(policy_assignment_name), 0))
        except jmespath.exceptions.JMESPathTypeError:  # ok if query fails on None result
            pass

        # but enable --show-all works
        self.cmd('policy assignment list --disable-scope-strict-match',
                 checks=JCheck("length([?name=='{}'])".format(policy_assignment_name), 1))

        # delete the assignment
        self.cmd('policy assignment delete -n {} -g {}'.format(policy_assignment_name, resource_group))
        self.cmd('policy assignment list --disable-scope-strict-match')

        # delete the policy
        self.cmd('policy definition delete -n {}'.format(policy_name))
        time.sleep(10)  # ensure the policy is gone when run live.
        self.cmd('policy definition list', checks=JCheck("length([?name=='{}'])".format(policy_name), 0))


class ManagedAppDefinitionScenarioTest(ScenarioTest):
    @ResourceGroupPreparer()
    def test_managedappdef(self, resource_group):
        location = 'westcentralus'
        appdef_name = 'testappdefname'
        appdef_display_name = 'test_appdef_123'
        appdef_description = 'test_appdef_123'
        packageUri = 'https:\/\/wud.blob.core.windows.net\/appliance\/SingleStorageAccount.zip'
        auth = '5e91139a-c94b-462e-a6ff-1ee95e8aac07:8e3af657-a8ff-443c-a75c-2fe8c4bcb635'
        lock = 'None'

        # create a managedapp definition
        create_cmd = 'managedapp definition create -n {} --package-file-uri {} --display-name {} --description {} -l {} -a {} --lock-level {} -g {}'
        appdef = self.cmd(create_cmd.format(appdef_name, packageUri, appdef_display_name, appdef_description, location, auth, lock, resource_group), checks=[
            JCheck('name', appdef_name),
            JCheck('displayName', appdef_display_name),
            JCheck('description', appdef_description),
            JCheck('authorizations[0].principalId', '5e91139a-c94b-462e-a6ff-1ee95e8aac07'),
            JCheck('authorizations[0].roleDefinitionId', '8e3af657-a8ff-443c-a75c-2fe8c4bcb635'),
            JCheck('artifacts[0].name', 'ApplianceResourceTemplate'),
            JCheck('artifacts[0].type', 'Template'),
            JCheck('artifacts[1].name', 'CreateUiDefinition'),
            JCheck('artifacts[1].type', 'Custom')
        ]).get_output_in_json()

        # list and show it
        list_cmd = 'managedapp definition list -g {}'
        self.cmd(list_cmd.format(resource_group), checks=[
            JCheck('[0].name', appdef_name)
        ])

        show_cmd = 'managedapp definition show --ids {}'
        self.cmd(show_cmd.format(appdef['id']), checks=[
            JCheck('name', appdef_name),
            JCheck('displayName', appdef_display_name),
            JCheck('description', appdef_description),
            JCheck('authorizations[0].principalId', '5e91139a-c94b-462e-a6ff-1ee95e8aac07'),
            JCheck('authorizations[0].roleDefinitionId', '8e3af657-a8ff-443c-a75c-2fe8c4bcb635'),
            JCheck('artifacts[0].name', 'ApplianceResourceTemplate'),
            JCheck('artifacts[0].type', 'Template'),
            JCheck('artifacts[1].name', 'CreateUiDefinition'),
            JCheck('artifacts[1].type', 'Custom')
        ])

        # delete
        self.cmd('managedapp definition delete -g {} -n {}'.format(resource_group, appdef_name))
        self.cmd('managedapp definition list -g {}'.format(resource_group), checks=NoneCheck())


class ManagedAppScenarioTest(ScenarioTest):
    @ResourceGroupPreparer()
    def test_managedapp(self, resource_group):
        location = 'westcentralus'
        appdef_name = 'testappdefname'
        appdef_display_name = 'test_appdef_123'
        appdef_description = 'test_appdef_123'
        packageUri = 'https:\/\/wud.blob.core.windows.net\/appliance\/SingleStorageAccount.zip'
        auth = '5e91139a-c94b-462e-a6ff-1ee95e8aac07:8e3af657-a8ff-443c-a75c-2fe8c4bcb635'
        lock = 'None'

        # create a managedapp definition
        create_cmd = 'managedapp definition create -n {} --package-file-uri {} --display-name {} --description {} -l {} -a {} --lock-level {} -g {}'
        managedappdef = self.cmd(create_cmd.format(appdef_name, packageUri, appdef_display_name,
                                                   appdef_description, location, auth, lock, resource_group)).get_output_in_json()

        # create a managedapp
        managedapp_name = 'mymanagedapp'
        managedapp_loc = 'westcentralus'
        managedapp_kind = 'servicecatalog'
        newrg = self.create_random_name('climanagedapp', 25)
        managedrg = '/subscriptions/{}/resourceGroups/{}'.format(managedappdef['id'].split("/")[2], newrg)
        create_cmd = 'managedapp create -n {} -g {} -l {} --kind {} -m {} -d {}'
        app = self.cmd(create_cmd.format(managedapp_name, resource_group, managedapp_loc, managedapp_kind, managedrg, managedappdef['id']), checks=[
            JCheck('name', managedapp_name),
            JCheck('type', 'Microsoft.Solutions/appliances'),
            JCheck('kind', 'servicecatalog'),
            JCheck('managedResourceGroupId', managedrg),
            JCheck('applianceDefinitionId', managedappdef['id'])
        ]).get_output_in_json()

        # list and show
        list_byrg_cmd = 'managedapp list -g {}'
        self.cmd(list_byrg_cmd.format(resource_group), checks=[
            JCheck('[0].name', managedapp_name)
        ])

        show_cmd = 'managedapp show --ids {}'
        self.cmd(show_cmd.format(app['id']), checks=[
            JCheck('name', managedapp_name),
            JCheck('type', 'Microsoft.Solutions/appliances'),
            JCheck('kind', 'servicecatalog'),
            JCheck('managedResourceGroupId', managedrg),
            JCheck('applianceDefinitionId', managedappdef['id'])
        ])

        # delete
        self.cmd('managedapp delete -g {} -n {}'.format(resource_group, managedapp_name))
        self.cmd('managedapp list -g {}'.format(resource_group), checks=NoneCheck())


class CrossRGDeploymentScenarioTest(ScenarioTest):

    @ResourceGroupPreparer(name_prefix='cli_test_cross_rg_alt', parameter_name='resource_group_cross')
    @ResourceGroupPreparer(name_prefix='cli_test_cross_rg_deploy')
    def test_group_deployment_crossrg(self, resource_group, resource_group_cross):
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        template_file = os.path.join(curr_dir, 'crossrg_deploy.json').replace('\\', '\\\\')
        deployment_name = 'azure-cli-crossrgdeployment'
        storage_account_1 = create_random_name(prefix='crossrg')
        storage_account_2 = create_random_name(prefix='crossrg')

        self.cmd('group deployment validate -g {} --template-file {} --parameters CrossRg={} StorageAccountName1={} StorageAccountName2={}'.format(
            resource_group, template_file, resource_group_cross, storage_account_1, storage_account_2), checks=[
            JCheck('properties.provisioningState', 'Succeeded')
        ])
        self.cmd('group deployment create -g {} -n {} --template-file {} --parameters CrossRg={}'.format(
            resource_group, deployment_name, template_file, resource_group_cross), checks=[
            JCheck('properties.provisioningState', 'Succeeded'),
            JCheck('resourceGroup', resource_group),
        ])
        self.cmd('group deployment list -g {}'.format(resource_group), checks=[
            JCheck('[0].name', deployment_name),
            JCheck('[0].resourceGroup', resource_group)
        ])
        self.cmd('group deployment show -g {} -n {}'.format(resource_group, deployment_name), checks=[
            JCheck('name', deployment_name),
            JCheck('resourceGroup', resource_group)
        ])
        self.cmd('group deployment operation list -g {} -n {}'.format(resource_group, deployment_name), checks=[
            JCheck('length([])', 3),
            JCheck('[0].resourceGroup', resource_group)
        ])


if __name__ == '__main__':
    unittest.main()
