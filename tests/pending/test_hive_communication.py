#!/usr/bin/env python3
"""
Unit tests for Cross-Hive Communication System
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from shared.communication.hive_communication import (
    CommunicationChannel,
    CommunicationMetrics,
    CommunicationProtocol,
    HiveCommunicationSystem,
    HiveMessage,
    MessageDeliveryStatus,
    MessagePriority,
    MessageType,
)
from shared.models.orchestration_node import NodeStatus, NodeType, OrchestrationNode, Priority


class TestHiveCommunicationSystem:
    """Test suite for Cross-Hive Communication System"""

    def setup_method(self):
        """Setup test fixtures"""
        self.comm_system = HiveCommunicationSystem()

        # Create test hives
        self.hive_1 = OrchestrationNode(
            requirement="Hive 1 - Authentication Service",
            node_type=NodeType.FEATURE,
            priority=Priority.HIGH,
        )

        self.hive_2 = OrchestrationNode(
            requirement="Hive 2 - Data Processing Service",
            node_type=NodeType.FEATURE,
            priority=Priority.NORMAL,
        )

        self.hive_3 = OrchestrationNode(
            requirement="Hive 3 - Analytics Service",
            node_type=NodeType.FEATURE,
            priority=Priority.LOW,
        )

    def test_communication_system_initialization(self):
        """Test communication system initialization"""
        assert self.comm_system is not None
        assert hasattr(self.comm_system, "registered_hives")
        assert hasattr(self.comm_system, "message_queue")
        assert hasattr(self.comm_system, "communication_active")

    def test_message_type_enum(self):
        """Test MessageType enum values"""
        assert MessageType.REQUEST.value == "request"
        assert MessageType.RESPONSE.value == "response"
        assert MessageType.NOTIFICATION.value == "notification"
        assert MessageType.COORDINATION.value == "coordination"
        assert MessageType.RESOURCE_SHARE.value == "resource_share"
        assert MessageType.STATUS_UPDATE.value == "status_update"
        assert MessageType.DEPENDENCY_SIGNAL.value == "dependency_signal"
        assert MessageType.EMERGENCY.value == "emergency"

    def test_message_priority_enum(self):
        """Test MessagePriority enum values"""
        assert MessagePriority.LOW.value == 1
        assert MessagePriority.NORMAL.value == 5
        assert MessagePriority.HIGH.value == 8
        assert MessagePriority.URGENT.value == 10

    def test_communication_protocol_enum(self):
        """Test CommunicationProtocol enum values"""
        assert CommunicationProtocol.DIRECT.value == "direct"
        assert CommunicationProtocol.BROADCAST.value == "broadcast"
        assert CommunicationProtocol.MULTICAST.value == "multicast"
        assert CommunicationProtocol.PUBLISH_SUBSCRIBE.value == "pub_sub"

    @pytest.mark.asyncio
    async def test_hive_registration(self):
        """Test hive registration"""
        # Register hive
        registration_result = await self.comm_system.register_hive(
            self.hive_1,
            {"communication_endpoints": ["auth_service"], "capabilities": ["authentication"]},
        )

        assert registration_result["success"] is True
        assert self.hive_1.node_id in self.comm_system.registered_hives

    @pytest.mark.asyncio
    async def test_hive_deregistration(self):
        """Test hive deregistration"""
        # Register first
        await self.comm_system.register_hive(self.hive_1, {})

        # Then deregister
        deregistration_result = await self.comm_system.deregister_hive(self.hive_1.node_id)

        assert deregistration_result["success"] is True
        assert self.hive_1.node_id not in self.comm_system.registered_hives

    @pytest.mark.asyncio
    async def test_start_communication_system(self):
        """Test starting communication system"""
        hives = [self.hive_1, self.hive_2, self.hive_3]

        start_result = await self.comm_system.start_communication_system(hives)

        assert start_result["success"] is True
        assert self.comm_system.communication_active is True
        assert len(self.comm_system.registered_hives) == 3

    @pytest.mark.asyncio
    async def test_stop_communication_system(self):
        """Test stopping communication system"""
        # Start first
        await self.comm_system.start_communication_system([self.hive_1])

        # Then stop
        stop_result = await self.comm_system.stop_communication_system()

        assert stop_result["success"] is True
        assert self.comm_system.communication_active is False

    def test_hive_message_creation(self):
        """Test hive message creation"""
        message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=MessageType.REQUEST,
            content={"request": "user_data", "user_id": "123"},
            priority=MessagePriority.HIGH,
            protocol=CommunicationProtocol.DIRECT,
            created_at=datetime.now(),
        )

        assert message.sender_id == self.hive_1.node_id
        assert message.recipient_id == self.hive_2.node_id
        assert message.message_type == MessageType.REQUEST
        assert message.priority == MessagePriority.HIGH

    @pytest.mark.asyncio
    async def test_send_direct_message(self):
        """Test sending direct message between hives"""
        # Register hives
        await self.comm_system.register_hive(self.hive_1, {})
        await self.comm_system.register_hive(self.hive_2, {})

        message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=MessageType.REQUEST,
            content={"request": "process_data", "data": [1, 2, 3]},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.DIRECT,
        )

        with patch.object(
            self.comm_system, "_deliver_message", new_callable=AsyncMock
        ) as mock_deliver:
            mock_deliver.return_value = MessageDeliveryStatus.DELIVERED

            delivery_status = await self.comm_system.send_message(message)

            assert delivery_status == MessageDeliveryStatus.DELIVERED
            mock_deliver.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_broadcast_message(self):
        """Test sending broadcast message to all hives"""
        # Register multiple hives
        hives = [self.hive_1, self.hive_2, self.hive_3]
        for hive in hives:
            await self.comm_system.register_hive(hive, {})

        broadcast_message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id="*",  # Broadcast to all
            message_type=MessageType.STATUS_UPDATE,
            content={"status": "processing_started", "timestamp": datetime.now().isoformat()},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.BROADCAST,
        )

        with patch.object(
            self.comm_system, "_deliver_broadcast_message", new_callable=AsyncMock
        ) as mock_broadcast:
            mock_broadcast.return_value = [
                MessageDeliveryStatus.DELIVERED,
                MessageDeliveryStatus.DELIVERED,
            ]

            delivery_statuses = await self.comm_system.send_message(broadcast_message)

            assert len(delivery_statuses) == 2  # Should deliver to 2 other hives
            mock_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_message(self):
        """Test receiving message by hive"""
        await self.comm_system.register_hive(self.hive_1, {})

        # Mock a message in the queue
        test_message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_2.node_id,
            recipient_id=self.hive_1.node_id,
            message_type=MessageType.RESPONSE,
            content={"response": "data_processed", "result": "success"},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.DIRECT,
        )

        # Add message to hive's message queue
        await self.comm_system._add_message_to_queue(self.hive_1.node_id, test_message)

        # Receive message
        received_messages = await self.comm_system.receive_messages(self.hive_1.node_id)

        assert len(received_messages) == 1
        assert received_messages[0].message_id == test_message.message_id

    @pytest.mark.asyncio
    async def test_request_response_pattern(self):
        """Test request-response communication pattern"""
        await self.comm_system.register_hive(self.hive_1, {})
        await self.comm_system.register_hive(self.hive_2, {})

        # Send request
        request = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=MessageType.REQUEST,
            content={"request": "get_user_info", "user_id": "123"},
            priority=MessagePriority.HIGH,
            protocol=CommunicationProtocol.DIRECT,
        )

        with patch.object(
            self.comm_system, "_deliver_message", new_callable=AsyncMock
        ) as mock_deliver:
            mock_deliver.return_value = MessageDeliveryStatus.DELIVERED

            # Mock response handler
            with patch.object(
                self.comm_system, "_handle_request_response", new_callable=AsyncMock
            ) as mock_handler:
                mock_response = HiveMessage(
                    message_id=str(uuid.uuid4()),
                    sender_id=self.hive_2.node_id,
                    recipient_id=self.hive_1.node_id,
                    message_type=MessageType.RESPONSE,
                    content={"user_info": {"name": "John", "email": "john@example.com"}},
                    priority=MessagePriority.HIGH,
                    protocol=CommunicationProtocol.DIRECT,
                    correlation_id=request.message_id,
                )
                mock_handler.return_value = mock_response

                response = await self.comm_system.send_request_and_wait_response(
                    request, timeout=5.0
                )

                assert response is not None
                assert response.correlation_id == request.message_id

    @pytest.mark.asyncio
    async def test_publish_subscribe_pattern(self):
        """Test publish-subscribe communication pattern"""
        # Register hives
        await self.comm_system.register_hive(self.hive_1, {})  # Publisher
        await self.comm_system.register_hive(self.hive_2, {})  # Subscriber
        await self.comm_system.register_hive(self.hive_3, {})  # Subscriber

        # Subscribe hives to a topic
        await self.comm_system.subscribe_to_topic(self.hive_2.node_id, "user_events")
        await self.comm_system.subscribe_to_topic(self.hive_3.node_id, "user_events")

        # Publish message
        publish_message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id="topic:user_events",
            message_type=MessageType.NOTIFICATION,
            content={"event": "user_created", "user_id": "456"},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.PUBLISH_SUBSCRIBE,
        )

        with patch.object(
            self.comm_system, "_deliver_to_subscribers", new_callable=AsyncMock
        ) as mock_deliver:
            mock_deliver.return_value = [
                MessageDeliveryStatus.DELIVERED,
                MessageDeliveryStatus.DELIVERED,
            ]

            delivery_statuses = await self.comm_system.send_message(publish_message)

            assert len(delivery_statuses) == 2  # Should deliver to 2 subscribers
            mock_deliver.assert_called_once()

    @pytest.mark.asyncio
    async def test_multicast_communication(self):
        """Test multicast communication to specific group"""
        # Register hives
        hives = [self.hive_1, self.hive_2, self.hive_3]
        for hive in hives:
            await self.comm_system.register_hive(hive, {})

        # Create multicast group
        group_members = [self.hive_2.node_id, self.hive_3.node_id]

        multicast_message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id="group:processing_hives",
            message_type=MessageType.COORDINATION,
            content={"coordination": "start_processing", "batch_id": "batch_001"},
            priority=MessagePriority.HIGH,
            protocol=CommunicationProtocol.MULTICAST,
            metadata={"group_members": group_members},
        )

        with patch.object(
            self.comm_system, "_deliver_to_group", new_callable=AsyncMock
        ) as mock_deliver:
            mock_deliver.return_value = [
                MessageDeliveryStatus.DELIVERED,
                MessageDeliveryStatus.DELIVERED,
            ]

            delivery_statuses = await self.comm_system.send_message(multicast_message)

            assert len(delivery_statuses) == 2
            mock_deliver.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_priority_handling(self):
        """Test message priority handling and ordering"""
        await self.comm_system.register_hive(self.hive_1, {})

        # Create messages with different priorities
        low_priority_msg = HiveMessage(
            message_id="low_priority",
            sender_id=self.hive_2.node_id,
            recipient_id=self.hive_1.node_id,
            message_type=MessageType.NOTIFICATION,
            content={"info": "low priority update"},
            priority=MessagePriority.LOW,
            protocol=CommunicationProtocol.DIRECT,
        )

        urgent_msg = HiveMessage(
            message_id="urgent",
            sender_id=self.hive_2.node_id,
            recipient_id=self.hive_1.node_id,
            message_type=MessageType.EMERGENCY,
            content={"alert": "system critical error"},
            priority=MessagePriority.URGENT,
            protocol=CommunicationProtocol.DIRECT,
        )

        # Add messages to queue
        await self.comm_system._add_message_to_queue(self.hive_1.node_id, low_priority_msg)
        await self.comm_system._add_message_to_queue(self.hive_1.node_id, urgent_msg)

        # Receive messages - urgent should come first
        received_messages = await self.comm_system.receive_messages(self.hive_1.node_id, limit=2)

        assert len(received_messages) == 2
        assert received_messages[0].message_id == "urgent"  # Urgent message first
        assert received_messages[1].message_id == "low_priority"  # Low priority second

    @pytest.mark.asyncio
    async def test_communication_metrics(self):
        """Test communication metrics collection"""
        await self.comm_system.register_hive(self.hive_1, {})
        await self.comm_system.register_hive(self.hive_2, {})

        # Send some messages to generate metrics
        message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=MessageType.REQUEST,
            content={"test": "metrics"},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.DIRECT,
        )

        with patch.object(self.comm_system, "_deliver_message", new_callable=AsyncMock):
            await self.comm_system.send_message(message)

        metrics = await self.comm_system.get_communication_metrics()

        assert isinstance(metrics, CommunicationMetrics)
        assert metrics.total_messages_sent >= 1
        assert metrics.active_hives >= 2

    @pytest.mark.asyncio
    async def test_communication_channel_creation(self):
        """Test communication channel creation and management"""
        channel = CommunicationChannel(
            channel_id="auth_data_channel",
            participants=[self.hive_1.node_id, self.hive_2.node_id],
            channel_type="dedicated",
            created_at=datetime.now(),
            is_active=True,
        )

        channel_created = await self.comm_system.create_communication_channel(channel)

        assert channel_created["success"] is True
        assert channel.channel_id in self.comm_system.communication_channels

    @pytest.mark.asyncio
    async def test_message_delivery_guarantees(self):
        """Test message delivery guarantees and retry mechanisms"""
        await self.comm_system.register_hive(self.hive_1, {})
        await self.comm_system.register_hive(self.hive_2, {})

        message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=MessageType.REQUEST,
            content={"critical": "data"},
            priority=MessagePriority.URGENT,
            protocol=CommunicationProtocol.DIRECT,
            delivery_guarantee="at_least_once",
            max_retries=3,
        )

        with patch.object(
            self.comm_system, "_deliver_with_retry", new_callable=AsyncMock
        ) as mock_retry:
            mock_retry.return_value = MessageDeliveryStatus.DELIVERED

            delivery_status = await self.comm_system.send_message(message)

            assert delivery_status == MessageDeliveryStatus.DELIVERED
            mock_retry.assert_called_once()

    @pytest.mark.asyncio
    async def test_communication_security(self):
        """Test communication security features"""
        # Test message encryption
        message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=MessageType.REQUEST,
            content={"sensitive": "data"},
            priority=MessagePriority.HIGH,
            protocol=CommunicationProtocol.DIRECT,
            encrypted=True,
        )

        encrypted_content = self.comm_system._encrypt_message_content(message.content)
        decrypted_content = self.comm_system._decrypt_message_content(encrypted_content)

        assert encrypted_content != message.content  # Should be encrypted
        assert decrypted_content == message.content  # Should decrypt correctly

    @pytest.mark.asyncio
    async def test_communication_analytics(self):
        """Test communication analytics and insights"""
        await self.comm_system.start_communication_system([self.hive_1, self.hive_2])

        # Generate some communication activity
        for i in range(5):
            message = HiveMessage(
                message_id=f"msg_{i}",
                sender_id=self.hive_1.node_id,
                recipient_id=self.hive_2.node_id,
                message_type=MessageType.REQUEST,
                content={"test": f"message_{i}"},
                priority=MessagePriority.NORMAL,
                protocol=CommunicationProtocol.DIRECT,
            )

            with patch.object(self.comm_system, "_deliver_message", new_callable=AsyncMock):
                await self.comm_system.send_message(message)

        analytics = await self.comm_system.get_communication_analytics()

        assert "message_patterns" in analytics
        assert "communication_efficiency" in analytics
        assert "network_topology" in analytics

    @pytest.mark.asyncio
    async def test_error_handling_invalid_recipient(self):
        """Test error handling for invalid recipient"""
        message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id="invalid_hive_id",
            message_type=MessageType.REQUEST,
            content={"test": "invalid recipient"},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.DIRECT,
        )

        delivery_status = await self.comm_system.send_message(message)

        assert delivery_status == MessageDeliveryStatus.FAILED

    @pytest.mark.asyncio
    async def test_communication_timeout_handling(self):
        """Test communication timeout handling"""
        await self.comm_system.register_hive(self.hive_1, {})
        await self.comm_system.register_hive(self.hive_2, {})

        request = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=MessageType.REQUEST,
            content={"request": "slow_operation"},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.DIRECT,
        )

        # Test timeout scenario
        with patch.object(
            self.comm_system, "_handle_request_response", new_callable=AsyncMock
        ) as mock_handler:
            # Simulate slow response
            async def slow_response(*args, **kwargs):
                await asyncio.sleep(2.0)  # Slower than timeout
                return None

            mock_handler.side_effect = slow_response

            response = await self.comm_system.send_request_and_wait_response(
                request, timeout=1.0  # 1 second timeout
            )

            assert response is None  # Should timeout

    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self):
        """Test concurrent message handling"""
        await self.comm_system.start_communication_system([self.hive_1, self.hive_2, self.hive_3])

        # Send multiple messages concurrently
        messages = []
        for i in range(10):
            message = HiveMessage(
                message_id=f"concurrent_msg_{i}",
                sender_id=self.hive_1.node_id,
                recipient_id=self.hive_2.node_id,
                message_type=MessageType.NOTIFICATION,
                content={"sequence": i},
                priority=MessagePriority.NORMAL,
                protocol=CommunicationProtocol.DIRECT,
            )
            messages.append(message)

        with patch.object(
            self.comm_system, "_deliver_message", new_callable=AsyncMock
        ) as mock_deliver:
            mock_deliver.return_value = MessageDeliveryStatus.DELIVERED

            # Send all messages concurrently
            tasks = [self.comm_system.send_message(msg) for msg in messages]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All messages should be delivered
            assert len(results) == 10
            assert all(
                status == MessageDeliveryStatus.DELIVERED
                for status in results
                if not isinstance(status, Exception)
            )

    @pytest.mark.parametrize(
        "message_type,expected_handling",
        [
            (MessageType.EMERGENCY, "immediate"),
            (MessageType.REQUEST, "standard"),
            (MessageType.NOTIFICATION, "standard"),
            (MessageType.STATUS_UPDATE, "standard"),
        ],
    )
    @pytest.mark.asyncio
    async def test_message_type_handling(self, message_type, expected_handling):
        """Test different message type handling"""
        message = HiveMessage(
            message_id=str(uuid.uuid4()),
            sender_id=self.hive_1.node_id,
            recipient_id=self.hive_2.node_id,
            message_type=message_type,
            content={"test": "message"},
            priority=MessagePriority.NORMAL,
            protocol=CommunicationProtocol.DIRECT,
        )

        handling_strategy = self.comm_system._determine_message_handling_strategy(message)

        if message_type == MessageType.EMERGENCY:
            assert handling_strategy == "immediate"
        else:
            assert handling_strategy == "standard"
