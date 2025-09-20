import boto3
from pprint import pprint
import sys
import base64

aws_session=boto3.session.Session(profile_name='Admin2')
ec2_client=aws_session.client(service_name='ec2', region_name='us-east-1')
ec2_res=aws_session.resource(service_name='ec2', region_name='us-east-1')
#1- create the vpc
create_VPC = ec2_client.create_vpc(CidrBlock='10.0.0.0/16')
vpc_id = create_VPC['Vpc']['VpcId']
print(f"new vpc created with vpc_id: {vpc_id}")

#2-create public subnets
AV_Zones=['us-east-1a','us-east-1b']
public_subnet_ciders=['10.0.10.0/24','10.0.20.0/24']
public_subnets_id=[]
for az,cider in zip(AV_Zones,public_subnet_ciders):
  create_public_subnet=ec2_client.create_subnet( AvailabilityZone=az, CidrBlock=cider,VpcId=vpc_id)
  public_subnets_id.append(create_public_subnet['Subnet']['SubnetId'])
print(f"public subnets are successfully created, public_subnet1_id: {public_subnets_id[0]} and public_subnet2_id: {public_subnets_id[1]}")

#3-auto assigned public ip address to EC2-instances at launched
for subnet_id in public_subnets_id:
  ec2_client.modify_subnet_attribute(SubnetId=subnet_id,
MapPublicIpOnLaunch={
        'Value': True})

#4-create Private subnet
private_subnet_ciders=['10.0.100.0/24','10.0.200.0/24']
private_subnets_id= []
for az,cider in zip(AV_Zones,private_subnet_ciders):
  create_private_subnet=ec2_client.create_subnet( AvailabilityZone=az, CidrBlock=cider,VpcId=vpc_id)
  private_subnets_id.append(create_private_subnet['Subnet']['SubnetId'])
print(f"private subnets are successfully created, public_subnet1_id: {private_subnets_id[0]} and public_subnet2_id: {private_subnets_id[1]}")
private_subnet1_id=private_subnets_id[0]
private_subnet2_id=private_subnets_id[1]
#5-create internet GetWay
create_IGW = ec2_client.create_internet_gateway()
IGW_id = create_IGW['InternetGateway']['InternetGatewayId']
print(f"IGW created with IGW_id: {IGW_id}")

#6-attach IGW to VPC
attach_igw = ec2_client.attach_internet_gateway(InternetGatewayId=IGW_id,VpcId=vpc_id)

#7-create RT for public subnets
create_public_RT = ec2_client.create_route_table(VpcId=vpc_id)
public_RT_id=create_public_RT['RouteTable']['RouteTableId']
print(f"public RT created with public_RT_id: {public_RT_id}")

#8-create route to public RT to traffic to internet through IGW
response = ec2_client.create_route(

    RouteTableId=public_RT_id,
    DestinationCidrBlock='0.0.0.0/0',
    GatewayId=IGW_id)

#9-associate public subnets to public RT
for subnet in public_subnets_id:
 ec2_client.associate_route_table(
    SubnetId=subnet,
    RouteTableId=public_RT_id
)
 print("public subnets are successfully associated to public RT")

#10-create private RT
create_private_RT = ec2_client.create_route_table(VpcId=vpc_id)
Private_RT_id=create_private_RT['RouteTable']['RouteTableId']
print(f"Private RT created with Private_RT_id: {Private_RT_id}")
#11-associate private subnets to private RT
for subnet in private_subnets_id:
 ec2_client.associate_route_table(
    SubnetId=subnet,
    RouteTableId=Private_RT_id
)
print("Private subnets are successfully associated to Private RT")

#12-allocate elastic ip address
elastic_ip =  ec2_client.allocate_address( Domain='vpc')
allocation_id = elastic_ip['AllocationId']

#13-create NAT GW
create_NAT_GW = ec2_client.create_nat_gateway(
    AllocationId=allocation_id,
    SubnetId=public_subnets_id[0])
nat_gw_id = create_NAT_GW['NatGateway']['NatGatewayId']
print(f"NAT GW created with nat_gw_id: {nat_gw_id}")

#14-sure that NAT GW exactly created and available
waiter = ec2_client.get_waiter('nat_gateway_available')
print("NAT Gateway is starting....")
waiter.wait( NatGatewayIds=[nat_gw_id])
print("NAT Gateway is available Now")

#15-add default route to private RT to traffic to internet through NAT GW
NAT_GW_route = ec2_client.create_route(
    RouteTableId=Private_RT_id,
    DestinationCidrBlock='0.0.0.0/0',
    NatGatewayId=nat_gw_id)

#16-create Security group for servers
web_SG = ec2_client.create_security_group(
    Description='SG for ec2 instances',
    GroupName='webSG',
    VpcId=vpc_id,

)
web_SG_id = web_SG['GroupId']
print(f"Web Security Group is created with web_SG_ID: {web_SG_id}")

#17-add inbound rule for ports [22,80,443] for web SG
add_inbound_webSG = ec2_client.authorize_security_group_ingress(

    GroupId=web_SG_id,

    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,

            'IpRanges': [
                {
                    'Description': 'allow SSH',
                    'CidrIp': '0.0.0.0/0'
                },
            ]


        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,

            'IpRanges': [
                {
                    'Description': 'allow HTTP',
                    'CidrIp': '0.0.0.0/0'
                },
            ]

        },
        {
            'IpProtocol': 'tcp',
            'FromPort': 443,
            'ToPort': 443,

            'IpRanges': [
                {
                    'Description': 'allow HTTPS',
                    'CidrIp': '0.0.0.0/0'
                },
            ]

        }
    ])
print(" inbound rules for ports [22,80,443] are successfully added for web SG ")

# 18- add egress rule to the WebSG - allowing traffic for updates and download any required packages.
ec2_client.authorize_security_group_egress(
    GroupId=web_SG_id,
    IpPermissions=[
        {
            'FromPort': 0,
            'ToPort': 0,
            'IpProtocol': 'tcp',
            'IpRanges': [
                {
                    'CidrIp': '0.0.0.0/0',
                },
            ],
        },
    ],
)

#19-launch EC2-instances in private subnets
user_data_script1 = '''#!/bin/bash
yum update -y
yum install httpd -y
systemctl start httpd
systemctl enable httpd
echo "This is server *1* in AWS Region US-EAST-1 in AZ US-EAST-1A" > /var/www/html/index.html
'''
user_data_script2 = '''#!/bin/bash
yum update -y
yum install httpd -y
systemctl start httpd
systemctl enable httpd
echo "This is server *2* in AWS Region US-EAST-1 in AZ US-EAST-1B" > /var/www/html/index.html
'''
instances_id=[]
user_data_script=[user_data_script1,user_data_script2]
for subnet,user_data in zip(private_subnets_id,user_data_script):
    run_instance=ec2_client.run_instances(
    BlockDeviceMappings=[
        {
            'Ebs': {
                'DeleteOnTermination': True ,
                'VolumeSize': 8,
                'VolumeType':  'gp2' ,
                'Encrypted': True
                },
                'DeviceName': '/dev/xvda',

        },
    ],
    ImageId='ami-08982f1c5bf93d976',
    InstanceType='t2.micro',
    KeyName='nattestKey', #Key pair
    MaxCount=1,
    MinCount=1,
    SecurityGroupIds=[
        web_SG_id,
    ],
    SubnetId=subnet,
    UserData=user_data,
)
    instances_id.append(run_instance['Instances'][0]['InstanceId'])

#'''20-waiter for check that all instances created and running'''
waiter = ec2_client.get_waiter('instance_running')
print("Web servers[instances] are being started ......")
waiter.wait(
    InstanceIds=instances_id
)
print("Web servers[instances] are running now ")
print(f"2 instances are successfully created, with instance1_id: {instances_id[0]} and instance2_id: {instances_id[1]}")

#21-create  a Client Object For ELB , Auto Scaling
elb_client = boto3.client(service_name='elbv2', region_name='us-east-1')
auto_scaling_client = boto3.client(service_name='autoscaling', region_name='us-east-1')

#22-create target group
web_TG = elb_client.create_target_group(
    Name='WEB-TG',
    Protocol='HTTP',
    Port=80,
    VpcId=vpc_id,
    HealthCheckProtocol='HTTP',
    HealthCheckPort="80",
    HealthCheckEnabled=True,
    HealthCheckPath='/',
    TargetType='instance',
)
web_TG_ARN=web_TG['TargetGroups'][0]['TargetGroupArn']
print(f"WEB_TG is successfully created with TargetGroupARN: {web_TG_ARN}")

#23-register Targets to web_TG
for instance_id in instances_id:
    elb_client.register_targets(
    TargetGroupArn=web_TG_ARN,
    Targets=[
        {
            'Id': instance_id,
            'Port': 80
        },
    ]
)
print("web servers[instances] are  rgistering  successfully to web_TG ")

#24-creating the Load Balancer Security Group
ALB_SG = ec2_client.create_security_group(
    Description='SG for Load Balancer',
    GroupName='ALB-SG',
    VpcId=vpc_id,

)
ALB_SG_id = ALB_SG['GroupId']
print(f"ALB Security Group is created with ALB_SG_id: {ALB_SG_id}")

#25-add inbound rule for ports [80] for ALB SG, allow HTTP traffic to inbound
add_inbound_ALBSG = ec2_client.authorize_security_group_ingress(

    GroupId=ALB_SG_id,
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'IpRanges': [
                {
                    'Description': 'allow HTTP',
                    'CidrIp': '0.0.0.0/0'
                },
            ]
        }
    ]
)
#26-add inbound rule for ports [80] for web SG, allow HTTP traffic from ALB SG
Web_SG_inbound_rule = ec2_client.authorize_security_group_ingress(
    GroupId=web_SG_id,
    IpPermissions=[
        {
            'IpProtocol': 'tcp',
            'FromPort': 80,
            'ToPort': 80,
            'UserIdGroupPairs': [
                {
                    'GroupId': ALB_SG_id,
                },
            ],
        },
    ]
)

#27-creat Application Load Balancer
create_elb = elb_client.create_load_balancer(
    Name='python-LB',
    Subnets= public_subnets_id ,
    SecurityGroups=[ ALB_SG_id ],
    Scheme='internet-facing',
    Type='application',
    IpAddressType='ipv4',
)
ALB_arn=create_elb['LoadBalancers'][0]['LoadBalancerArn']
ALB_DNS=create_elb['LoadBalancers'][0]['DNSName']

'''Ensure That ALB is Up and Available'''
waiter = elb_client.get_waiter('load_balancer_available')
print ("ALB is being started ......")
waiter.wait()
waiter.wait(LoadBalancerArns=[ ALB_arn ] )
print("ALB is Up and Available Now")
print(f"ALB is created successfully with ALB_ARN: {ALB_arn}, and with ALB_DNS: {ALB_DNS}")

#28-create listeners
create_listener = elb_client.create_listener(
    LoadBalancerArn=ALB_arn,
    Protocol='HTTP',
    Port=80,
DefaultActions=[
        {
            'Type': 'forward',
            'TargetGroupArn': web_TG_ARN}
]
)
print("ALB listener is created successfully ")

#29- create Launch Template
AV_Zones=['us-east-1a','us-east-1b']
user_data_script = """#!/bin/bash
yum update -y
yum install httpd -y
systemctl start httpd
systemctl enable httpd
echo "This is an auto scaling web server in AWS Region US-EAST-1 " > /var/www/html/index.html
"""
launch_template = ec2_client.create_launch_template(
    LaunchTemplateName="python-web-template",
    LaunchTemplateData={
        "ImageId": "ami-08982f1c5bf93d976",
        "InstanceType": "t2.micro",
        "KeyName": "nattestKey",
        "SecurityGroupIds": [web_SG_id],
        "UserData":  base64.b64encode(user_data_script.encode("utf-8")).decode("utf-8")
    }
)
print("Launch Template created successfully")

#30 create Auto Scaling Group
auto_scaling_client = boto3.client("autoscaling", region_name="us-east-1")
create_asg = auto_scaling_client.create_auto_scaling_group(
    AutoScalingGroupName="my-auto-scaling-group",
    LaunchTemplate={
        "LaunchTemplateName": "python-web-template",
        "Version": "$Latest"
    },
    MinSize=1,
    MaxSize=4,
    DesiredCapacity=3,
    AvailabilityZones=AV_Zones,
    VPCZoneIdentifier = ",".join([private_subnet1_id, private_subnet2_id]),
    TargetGroupARNs=[web_TG_ARN]
)
describe_auto_scaling_group = auto_scaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=['my-auto-scaling-group'])
print (f"auto_scaling_group is created successfully with ARN: {describe_auto_scaling_group['AutoScalingGroups'][0]['AutoScalingGroupARN']}")



# 25 - create the RDS DataBase and its security group
rds_client = aws_session.client('rds', region_name='us-east-1')

# Create Security Group for DB
DB_SG = ec2_client.create_security_group(
    Description='SG for Database',
    GroupName='db_SG',
    VpcId=vpc_id,
    TagSpecifications=[
        {
            'ResourceType': 'security-group',
            'Tags': [
                {'Key': 'Name', 'Value': 'DB_SG'}
            ]
        },
    ],
)
DB_SG_ID = DB_SG['GroupId']
print(f"Security Group DB_SG created successfully, ID: {DB_SG_ID}")

# Allow access from WebSG only
ec2_client.authorize_security_group_ingress(
    GroupId=DB_SG_ID,
    IpPermissions=[
        {
            'FromPort': 0,
            'ToPort': 0,
            'IpProtocol': '-1',
            'UserIdGroupPairs': [{'GroupId': web_SG_id}],
        },
    ],
)

# Create DB Subnet Group
rds_client.create_db_subnet_group(
    DBSubnetGroupDescription='RDS Databases Subnet Group',
    DBSubnetGroupName='myrdsdbsubnetgroup',
    SubnetIds=private_subnets_id
)

# Launch the RDS Instance
response = rds_client.create_db_instance(
    DBInstanceIdentifier='AppDBInstance',
    DBInstanceClass='db.t3.micro',      # Free Tier compatible
    Engine='mysql',
    EngineVersion='8.0.42',             # Supported on t2.micro
    AllocatedStorage=20,                # Minimum storage for Free Tier
    MasterUsername='admin',
    MasterUserPassword='abcde123',
    DBSubnetGroupName='myrdsdbsubnetgroup',
    VpcSecurityGroupIds=[DB_SG_ID],
    MultiAZ=False                        # Free Tier does not support Multi-AZ
)

rds_arn = response['DBInstance']['DBInstanceArn']
waiter = rds_client.get_waiter('db_instance_available')
print("RDS Instance is being started ......")
waiter.wait(DBInstanceIdentifier='AppDBInstance')
print("RDS Instance is up and available now")

rds = rds_client.describe_db_instances(DBInstanceIdentifier='AppDBInstance')
rds_address = rds['DBInstances'][0]['Endpoint']['Address']
print(f"RDS Instance created successfully! ARN: {rds_arn}, DNS: {rds_address}")
